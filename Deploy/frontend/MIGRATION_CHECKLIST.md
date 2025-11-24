# Checklist Migrazione Frontend

## ✅ Chiamate API Verificate

### Profile
- ✅ GET `/profile` - ✅ Implementato
- ✅ PUT `/profile` - ✅ Implementato

### Tenants
- ✅ GET `/tenants` - ✅ Implementato (filtra per reseller se necessario)
- ✅ GET `/tenants/{tenant_id}` - ✅ Implementato
- ✅ POST `/tenants` - ✅ Implementato (SuperAdmin e Reseller)
- ✅ DELETE `/tenants/{tenant_id}` - ✅ Implementato

### Users
- ✅ GET `/tenants/{tenant_id}/users` - ✅ Implementato
- ✅ GET `/users/{user_id}` - ✅ Implementato
- ✅ POST `/tenants/{tenant_id}/users` - ✅ Implementato
- ✅ PUT `/users/{user_id}` - ✅ Implementato
- ✅ DELETE `/users/{user_id}` - ✅ Implementato

### Resellers
- ✅ GET `/resellers` - ✅ Implementato (solo SuperAdmin)
- ✅ POST `/resellers` - ✅ Implementato (solo SuperAdmin)
- ✅ GET `/resellers/{reseller_id}/tenants` - ✅ Implementato
- ✅ POST `/resellers/assign-tenant` - ✅ Implementato
- ✅ POST `/resellers/remove-tenant` - ✅ Implementato

### Reports
- ⚠️ GET `/reports` - Endpoint esiste ma backend non implementato (era TODO anche nel frontend originale)
- ⚠️ GET `/tenants/{tenant_id}/reports` - Endpoint esiste ma backend non implementato (era TODO anche nel frontend originale)
- ⚠️ GET `/users/{user_id}/reports` - Endpoint esiste ma backend non implementato (era TODO anche nel frontend originale)

## ✅ Funzionalità Verificate

### Autenticazione
- ✅ Login con Cognito
- ✅ Cambio password obbligatorio al primo accesso
- ✅ Logout
- ✅ Gestione sessione

### SuperAdmin Dashboard
- ✅ Gestione Reseller (lista, creazione, assegnazione tenant, visualizzazione tenant)
- ✅ Gestione Tenant (lista, creazione, eliminazione)
- ⚠️ Report globali (era TODO nel frontend originale)

### Admin Dashboard
- ✅ Gestione Utenti (lista, creazione, modifica, eliminazione)
- ⚠️ Report tenant (era TODO nel frontend originale)

### User Dashboard
- ✅ Profilo utente (modifica nome, XML endpoint, XML token, report schedule)
- ⚠️ Report personali (era TODO nel frontend originale)

### Campi Form Utente
- ✅ Nome
- ✅ Email (non modificabile in edit)
- ✅ Email per Report (opzionale, può essere duplicata)
- ✅ XML Endpoint URL
- ✅ XML Token (opzionale)
- ✅ Report Enabled
- ✅ Report Schedule (frequency, time, day_of_week, day_of_month)
- ✅ Conversione UTC/Local time

## Note

I report erano già in sviluppo (TODO) nel frontend originale, quindi ho mantenuto lo stesso stato. Gli endpoint esistono nel template.yaml ma non sono implementati nel backend api.py.

