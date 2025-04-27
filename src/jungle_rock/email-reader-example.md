# ProtonMail Reader Usage Examples

After setting up the ProtonMail Bridge and configuring the Python script, you can use the following examples to filter emails based on your criteria.

## Basic Usage

### Fetch all unread emails (default behavior)
```bash
python protonmail_reader.py
```

### Fetch all emails (including read ones)
```bash
python protonmail_reader.py --all
```

### Limit the number of emails to fetch
```bash
python protonmail_reader.py --limit 50
```

## Filtering Emails

### Filter by sender
```bash
python protonmail_reader.py --sender "example@domain.com"
```

### Filter by subject keyword
```bash
python protonmail_reader.py --subject "Report"
```

### Filter by sender AND subject keyword
```bash
python protonmail_reader.py --sender "reports@company.com" --subject "Monthly"
```

## Date Filtering

### Get emails from a specific date onwards
```bash
python protonmail_reader.py --date-from 2023-01-01
```

### Get emails until a specific date
```bash
python protonmail_reader.py --date-to 2023-12-31
```

### Get emails within a date range
```bash
python protonmail_reader.py --date-from 2023-01-01 --date-to 2023-12-31
```

## Combined Filtering

### Get all unread emails from a specific sender with a keyword in the subject line from last month
```bash
python protonmail_reader.py --sender "reports@company.com" --subject "Financial" --date-from 2023-03-01
```

### Get all emails (including read) with specific criteria
```bash
python protonmail_reader.py --all --sender "notifications@service.com" --subject "Alert" --limit 200
```

## Cron Job Example

To set up a daily job that fetches emails with specific criteria, add this to your crontab:

```
# Run at 8:00 AM every day, fetching emails from reports@company.com with "Daily" in the subject
0 8 * * * cd /path/to/script && /usr/bin/python3 /path/to/script/protonmail_reader.py --sender "reports@company.com" --subject "Daily" > /path/to/logfile.log 2>&1
```

## Viewing Stored Emails

The emails are stored in the SQLite database specified in your config file. You can use any SQLite browser or the command line to view them:

```bash
sqlite3 emails.db "SELECT id, from_address, subject, date FROM emails"
```
