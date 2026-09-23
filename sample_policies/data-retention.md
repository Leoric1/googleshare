# Data Retention Policy

## Purpose
Defines how long Fake company retains different classes of data, and
when and how that data is disposed of.

## Retention schedule

| Data class              | Retention period | Disposal method           |
|-------------------------|------------------|---------------------------|
| Customer transaction records | 7 years     | Secure deletion           |
| Employee HR records     | 7 years after separation | Secure deletion    |
| Email (general)         | 3 years          | Automated purge           |
| Email (legal hold)      | Until release    | Manual review, then purge |
| Application access logs | 18 months        | Automated purge           |
| Security incident logs  | 5 years          | Secure deletion           |
| Marketing contact lists | Until opt-out + 30 days | Secure deletion    |

## Legal holds
Retention periods are extended indefinitely for any data subject to a legal
hold notice issued by the General Counsel's office. Do not delete data on
hold, even if its retention period has expired.

## Backups
Backups follow the same retention schedule as their source data. Offsite
backup tapes are destroyed per the schedule above.

## Policy owner
General Counsel + IT. Last reviewed 2026-02-01.
