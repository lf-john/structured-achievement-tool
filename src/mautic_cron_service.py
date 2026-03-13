# import subprocess # Removed, using default_api.run_shell_command instead


def get_mautic_container_id(run_shell_command_func):
    # This function will dynamically get the Mautic container ID
    command = "docker ps -q --filter ancestor=mautic/mautic"
    result = run_shell_command_func(command, description="Get Mautic container ID")
    if result.get("exit_code", 0) != 0:
        raise Exception(f"Failed to get Mautic container ID: {result.get('output', '')}")
    container_id = result.get("output", "").strip()
    if not container_id:
        raise Exception("Mautic container not found.")
    return container_id


def get_mautic_cron_schedule(run_shell_command_func):
    container_id = get_mautic_container_id(run_shell_command_func)
    # Attempt to read crontab inside the Mautic container
    command = f"docker exec {container_id} cat /etc/crontab"
    result = run_shell_command_func(command, description=f"Read /etc/crontab in container {container_id}")
    if result.get("exit_code", 0) != 0:
        # If /etc/crontab doesn't exist or is empty, try user-specific crontabs
        command = f"docker exec {container_id} ls /var/spool/cron/crontabs/"
        user_crontabs_list = run_shell_command_func(
            command, description=f"List user crontabs in container {container_id}"
        )
        if user_crontabs_list.get("exit_code", 0) == 0 and user_crontabs_list.get("output", "").strip():
            # Assuming 'root' or 'www-data' might have cron jobs
            for user_cron_file in user_crontabs_list.get("output", "").splitlines():
                command = f"docker exec {container_id} cat /var/spool/cron/crontabs/{user_cron_file}"
                user_cron_content = run_shell_command_func(
                    command, description=f"Read user crontab for {user_cron_file} in container {container_id}"
                )
                if user_cron_content.get("exit_code", 0) == 0 and "mautic:emails:send" in user_cron_content.get(
                    "output", ""
                ):
                    cron_lines = user_cron_content.stdout.splitlines()
                    for line in cron_lines:
                        if "mautic:emails:send" in line and not line.strip().startswith("#"):
                            return line.strip()
            raise ValueError("Mautic email send cron line not found in user crontabs.")
        raise Exception(f"Failed to get Mautic cron schedule: {result.get('output', '')}")

    cron_lines = result.get("output", "").splitlines()
    for line in cron_lines:
        if "mautic:emails:send" in line and not line.strip().startswith("#"):
            return line.strip()
    raise ValueError("Mautic email send cron line not found.")


def get_mautic_mailer_spool_msg_limit(run_shell_command_func):
    container_id = get_mautic_container_id(run_shell_command_func)
    # Search for mailer_spool_msg_limit in Mautic's configuration files
    # Common locations: /var/www/html/app/config/parameters.php or local.php
    search_paths = ["/var/www/html/app/config/parameters.php", "/var/www/html/app/config/local.php"]
    for path in search_paths:
        command = f"docker exec {container_id} cat {path}"
        result = run_shell_command_func(
            command, description=f"Read Mautic config file {path} in container {container_id}"
        )
        if result.get("exit_code", 0) == 0:
            for line in result.get("output", "").splitlines():
                if "mailer_spool_msg_limit" in line:
                    # Extract the value, assuming it's an integer
                    try:
                        value = int("".join(filter(str.isdigit, line)))
                        return str(value)
                    except ValueError:
                        pass
    raise ValueError("Mailer spool message limit not found.")


def analyze_effective_daily_send_limit(cron_line, msg_limit):
    # This is a simplified analysis. A real implementation would parse cron expressions.
    # For now, we'll assume a daily cron or check if msg_limit is present.
    if "0 8 * * *" in cron_line:  # Example for once a day at 8 AM
        return "Cron configured to run effectively once per day"
    elif msg_limit and int(msg_limit) > 0:
        return f"Mailer spool limit ({msg_limit}) effectively caps daily volume"
    return "Could not determine effective daily send limit."
