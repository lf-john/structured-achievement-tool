#!/usr/bin/env python3
import docker
import sys
from datetime import datetime, timezone

def get_container_health():
    """
    Checks the health of all Docker containers, focusing on specific services.
    Exits with 0 if all checks pass, 1 otherwise.
    """
    all_healthy = True
    try:
        client = docker.from_env()
    except docker.errors.DockerException:
        print("Error: Docker daemon is not running or accessible.", file=sys.stderr)
        return 1

    services_to_check = {
        "mautic": "8080",
        "suitecrm": "8088",
        "n8n": "8090"
    }
    
    report_data = []

    try:
        containers = client.containers.list(all=True)
    except Exception as e:
        print(f"Error: Could not list Docker containers. {e}", file=sys.stderr)
        return 1


    for container in containers:
        try:
            inspect_data = client.api.inspect_container(container.id)
        except docker.errors.NotFound:
            print(f"Warning: Container {container.name} not found during inspection, skipping.", file=sys.stderr)
            continue
        
        name = container.name
        status = container.status
        restart_count = inspect_data['RestartCount']
        
        # Uptime calculation
        uptime = "N/A"
        if status.startswith("Up"):
            try:
                start_time_str = inspect_data['State']['StartedAt']
                # Handle Docker's inconsistent time format
                if '.' in start_time_str:
                    start_time_str = start_time_str.split('.')[0] + 'Z'
                elif not start_time_str.endswith('Z'):
                    start_time_str += 'Z'
                
                start_time = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                uptime_delta = datetime.now(timezone.utc) - start_time
                uptime = str(uptime_delta).split('.')[0] # Remove microseconds
            except (ValueError, KeyError):
                uptime = "Error parsing start time"


        container_info = {
            "name": name,
            "status": status,
            "restarts": restart_count,
            "uptime": uptime,
            "notes": []
        }

        # Check restart count
        if restart_count > 3:
            container_info["notes"].append(f"High restart count: {restart_count}")
            all_healthy = False

        # Check port bindings for specific services
        for service_name, port in services_to_check.items():
            if service_name in name.lower():
                ports = inspect_data.get('HostConfig', {}).get('PortBindings')
                expected_port = f"{port}/tcp"
                if not ports or expected_port not in ports:
                    container_info["notes"].append(f"FAIL: Port {port} not bound!")
                    all_healthy = False
                else:
                    host_ports = [binding['HostPort'] for binding in ports[expected_port] if 'HostPort' in binding]
                    if host_ports:
                        container_info["notes"].append(f"OK: Port {port}->{', '.join(host_ports)}")
                    else:
                        container_info["notes"].append(f"FAIL: Port {port} bound but no host port!")
                        all_healthy = False


        report_data.append(container_info)

    # Print Report
    print(f"{'CONTAINER':<30} {'STATUS':<20} {'RESTARTS':<10} {'UPTIME':<20} {'NOTES'}")
    print("="*110)
    for info in report_data:
        notes_str = ", ".join(info['notes'])
        print(f"{info['name']:<30} {info['status']:<20} {info['restarts']:<10} {info['uptime']:<20} {notes_str}")

    return 0 if all_healthy else 1

if __name__ == "__main__":
    exit_code = get_container_health()
    if exit_code == 0:
        print("\n✓ All health checks passed.")
    else:
        print("\n✗ One or more health checks failed.")
    sys.exit(exit_code)
