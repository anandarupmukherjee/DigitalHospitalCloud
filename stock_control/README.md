# Inventory Management Starter Solution

Run with docker:  
-  `./setup_keys.sh`  
- `docker compose build`  
- `./start.sh`

Navigate to `localhost:8000` in a web browser.  
New items can be set up in the `Stock Management` tab. 

If you need to use the django admin page - for example to edit the unit cost or supplier link of an existing item,   
It can be accessed at `localhost:8000/admin` or is linked from the `Stock Management` tab.  
Log in with:  
- username: `admin`
- password: `shoestring`  

The Docker entrypoint automatically creates this superuser on startup.  
Override the credentials by setting `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`,  
and `DJANGO_SUPERUSER_EMAIL` in `docker-compose.yml` (or via your environment) before running `start.sh`.

## Safe upgrades and database preservation

Before making schema or deployment changes, create a backup of the current database state:

```bash
./backup_database.sh
```

For normal stack upgrades, use the upgrade wrapper instead of a plain `docker compose up` so the backup happens first:

```bash
./upgrade.sh
```

This creates a timestamped backup in `./backups/`, then rebuilds and restarts the stack. If you need to skip either step intentionally, use `SKIP_BACKUP=1` or `SKIP_BUILD=1`.

If you need to migrate from the local SQLite source database into Postgres, do not run `migrate_data.sh` unless you have a current backup. The migration script now protects existing Postgres data and requires an explicit overwrite flag:

```bash
FORCE_MIGRATE=1 ./migrate_data.sh
```

If `postgres_data` already exists, the script will stop unless `FORCE_MIGRATE=1` is set. When forced, it now preserves the existing Postgres data directory under `./backups/` instead of deleting it.

## Modular add-ons

The core inventory management experience always stays enabled. Optional add-ons now live under the `solutions/`
package and can be toggled without touching the code:

- `solutions.purchase_orders` – purchase order recording and delivery completion
- `solutions.quality_control` – QC checks for product lots
- `solutions.analytics` – withdrawals tracking, forecasting, and reporting

Flip modules on/off by editing `config/module_config.yaml`. Example:

```yaml
modules:
  inventory_core:
    enabled: true    # mandatory
  purchase_orders:
    enabled: true
  quality_control:
    enabled: false
  analytics:
    enabled: true
```

Restart the server after changing the config so Django reloads the enabled apps list.
