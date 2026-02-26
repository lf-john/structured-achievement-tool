def generate_cron_documentation(cron_line, modification_instructions):
    documentation = f"""
## Current `mautic:emails:send` Cron Schedule

```bash
{cron_line}
```

## Instructions for Modifying Cron Schedule

{modification_instructions}
"""
    return documentation
