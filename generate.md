# This is a Python script that will execute playbooks from the /playbooks dir and generate a report in the /reports dir
## Used for Meraki Auditing
- Meraki API
- Meraki Dashboard
- Meraki API Key
- Meraki Dashboard API Key
- Meraki Dashboard API Token

# Launcher is tkinter based 
 - select playbook
 - select report type
 - select report name
 
 # On start
 - Prompt for API Key
 - Prompt which Meraki networks to use
 - Load in all devices in selected networks
 - Button to load playbook
 - Preview of playbook
 - Button to execute playbook
 - Button to generate report
 - Button to save report
 - Button to exit

# Playbooks
- YAML based
- Abstracts out the API calls
- Restful in Nature

# Output
- CSV
- Formless headers (auto generated from API response)
- Date and time of execution
- To handle multiple API requests, folder structure is used each folder holds the output of each api request group (eg. all devices in a network, all interfaces in a device, all clients in a network)
- Playbook name
- Report name
- Report type
- Report version
- Report description
- Report author
- Report date
- Report time
- Report duration

