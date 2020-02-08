# Backup EC2

![.github/workflows/run.yml](https://github.com/creatio-au/backup-ec2/workflows/.github/workflows/run.yml/badge.svg)

Small program to run through a set of AWS accounts and backup all EC2 Machines.


## Requirements

 - Python 3
 - virtualenvwrapper


## Setting Up

1. Install dependencies

  ```bash
  mkvirtualenv -p python3 backup-ec2
  pip install -r requirements.txt
  ```

2. Add the details of your AWS accounts to the template.

  ```bash
  cp credentials.json.dist credentials.json
  vi credentials.json
  ```


## Running

```bash
python3 main.py
```
