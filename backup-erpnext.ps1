# =====================================================================
# ERPNext backup - chalao kisi bhi risky/bulk data-changing operation
# se PEHLE (jaisa 500-student seed ya bulk cleanup scripts).
#
#   .\backup-erpnext.ps1
#
# Frappe ka apna "bench backup" command use karta hai - database +
# site config, dono save hote hain frappe_test container ke andar:
#   sites/frontend/private/backups/
#
# Restore karne ke liye (agar kabhi zaroorat pare):
#   docker exec frappe_test-backend-1 bash -c "cd /home/frappe/frappe-bench && bench --site frontend restore <backup-file>.sql.gz"
# =====================================================================

Write-Host "Backing up ERPNext (site: frontend)..." -ForegroundColor Cyan

docker exec frappe_test-backend-1 sh -c "cd /home/frappe/frappe-bench && bench --site frontend backup"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nBackup done. Files are inside the container at:" -ForegroundColor Green
    Write-Host "  sites/frontend/private/backups/" -ForegroundColor Green
    Write-Host "`nTo copy the latest one out to this machine:" -ForegroundColor DarkGray
    Write-Host '  docker exec frappe_test-backend-1 sh -c "ls -t sites/frontend/private/backups/*.sql.gz | head -1"' -ForegroundColor DarkGray
    Write-Host "  docker cp frappe_test-backend-1:<path-from-above> ./erpnext-backups/" -ForegroundColor DarkGray
} else {
    Write-Host "`nBackup failed - check that the ERPNext containers are running." -ForegroundColor Red
}
