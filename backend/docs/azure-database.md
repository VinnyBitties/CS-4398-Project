# Shared database on Azure

The backend stores scans, stage reports and accounts in one database. With
`DATABASE_URL` set it uses that PostgreSQL server; without it, a local SQLite
file (`data/sentinel.db`). Pointing every teammate's backend at the same
Azure PostgreSQL server means everyone shares accounts and scan history.

The dashboard never connects to the database. Only the backend does:

```
Dashboard  ->  Backend (Node, on each laptop)  ->  Azure Database for PostgreSQL
                         ^
                DATABASE_URL in backend/.env (never committed)
```

## 1. Create the server (one person, once)

In the [Azure portal](https://portal.azure.com): **Create a resource** →
**Azure Database for PostgreSQL** → **Flexible server** → **Create**.

**Basics**

| Setting | Choose |
|---|---|
| Resource group | The one the sandbox VM is in, so the project's resources stay together |
| Server name | e.g. `coinflip-db`. Becomes `coinflip-db.postgres.database.azure.com` |
| Region | The sandbox VM's region |
| PostgreSQL version | 16 |
| Workload type | **Development** |
| Compute + storage | **Configure server**: **Burstable**, **Standard_B1ms**, **32 GiB** storage, high availability **off**, backup retention **7 days**, **locally redundant** backups |
| Authentication | **PostgreSQL authentication only** |
| Admin username / password | e.g. `sentineladmin`. See the password note in step 3 |

Storage can be increased later but never reduced, so start at 32 GiB.

**Networking**

- Connectivity method: **Public access (allowed IP addresses)**.
- Click **+ Add current client IP address** for your own machine. Add each
  teammate's IP too (they can find it at <https://whatismyipaddress.com>).
- Leave "Allow public access from any Azure service" **off**. It opens the
  server to every Azure customer's resources, not just ours.

**Review + create**: check the estimated monthly cost shown on this page
before clicking **Create**. The smallest Burstable server has historically
been covered for 12 months on eligible Azure free accounts; Azure for
Students accounts spend credit instead. Creation takes a few minutes.

## 2. Create the database

Open the new server → **Settings → Databases → + Add** → name it `sentinel`
→ **Save**. The backend creates its tables in it the first time it starts.

## 3. Build the connection string

```
postgres://sentineladmin:PASSWORD@coinflip-db.postgres.database.azure.com:5432/sentinel
```

Use your server name, admin username and password. A string copied from the
portal's **Connect** page that ends in `?sslmode=require` works as-is.

**Password note:** characters like `@ # / : ? %` break a URL. Either use a
password of letters, digits, `-` and `_` (make it long), or write those
characters encoded: `@` → `%40`, `#` → `%23`, `/` → `%2F`, `:` → `%3A`,
`?` → `%3F`, `%` → `%25`.

## 4. Point a backend at it

In `backend/.env` (copy `.env.example` if you have none):

```
DATABASE_URL=postgres://sentineladmin:...@coinflip-db.postgres.database.azure.com:5432/sentinel
```

Then `npm start`. The first lines should read:

```
Database: PostgreSQL (coinflip-db.postgres.database.azure.com/sentinel)
Sentinel backend listening on port 3000
```

To go back to your local SQLite file, comment the line out.

## 5. Share it with the team

- Send the connection string **privately** (a direct message or a password
  manager). It contains the admin password. Never commit `.env`, and don't
  paste it in a group chat or a doc.
- Each teammate's IP must be in the server's **Networking** firewall list.
  IPs change between home and campus Wi-Fi; if the backend says
  `Connection terminated due to connection timeout`, add your current IP.

## What a shared database changes

- **Accounts and history are shared.** An account made on one laptop logs in
  on any other. Your history shows your scans from every machine.
- **Each backend only runs its own scans.** An uploaded `.exe` is saved on the
  laptop that received it, so only that laptop's backend can scan it. Jobs
  record their owner (`WORKER_ID`, default: computer name + port). If you
  close your backend mid-scan, the scan resumes when you start it again; a
  teammate's backend won't pick it up.
- **Uploaded files stay local.** The database holds the hash, the original
  name and every report, not the executable itself.
- **Tests never touch Azure.** `npm test` uses an in-memory SQLite even when
  `.env` sets `DATABASE_URL`. To run the suite against a PostgreSQL test
  database, set `TEST_DATABASE_URL` and run `npm run test:pg`. Point it at a
  separate database, because the suite empties every table it runs against.

## Looking at the data

Use the portal's query editor, `psql`, or the VS Code PostgreSQL extension.
Reports are stored as JSONB, so you can query inside them:

```sql
-- Every scan that matched a known signature, newest first
SELECT s.id, coalesce(s.original_filename, s.submitted_url) AS item,
       r.report_json -> 'match' ->> 'name' AS matched, s.created_at
FROM samples s
JOIN results r ON r.sample_id = s.id AND r.stage = 'signature'
WHERE r.signature_match = 1
ORDER BY s.id DESC;
```

## Keeping the cost down

- The server bills while it runs. Between work sessions: server **Overview →
  Stop**. Azure starts it again automatically after 7 days.
- Delete the server (or its resource group) when the course ends.

## Troubleshooting

| Startup message | Fix |
|---|---|
| `Connection terminated due to connection timeout` | Your IP isn't in the firewall list, or the server is stopped. |
| `password authentication failed` | Wrong username or password in `DATABASE_URL`, or a special character in the password that isn't encoded. |
| `database "sentinel" does not exist` | Do step 2. |
| `The server does not support SSL connections` | Only for a PostgreSQL on your own machine: add `DATABASE_SSL=false`. Azure always uses TLS. |
