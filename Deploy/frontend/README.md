# Maya Analytics - Frontend Next.js

Frontend moderno per Maya Analytics costruito con Next.js, TypeScript e React.

## Struttura del Progetto

```
frontend-next/
├── app/                    # Next.js App Router
│   ├── layout.tsx         # Layout principale con AuthProvider
│   ├── page.tsx           # Pagina principale (routing)
│   └── globals.css        # Stili globali
├── components/            # Componenti React
│   ├── dashboards/        # Dashboard per ogni ruolo
│   ├── Dashboard.tsx      # Dashboard principale
│   ├── DashboardHeader.tsx
│   ├── LoginForm.tsx
│   └── ChangePasswordForm.tsx
├── contexts/              # React Contexts
│   └── AuthContext.tsx    # Context per autenticazione
├── lib/                   # Utility e configurazione
│   ├── api.ts            # Chiamate API
│   ├── cognito.ts        # Setup Cognito
│   ├── config.ts         # Configurazione
│   └── utils.ts          # Funzioni utility
└── types/                 # TypeScript types
    └── index.ts
```

## Setup

1. Installa le dipendenze:
```bash
npm install
```

2. Crea il file `.env.local` (vedi `.env.local.example`):
```bash
cp .env.local.example .env.local
```

3. Avvia il server di sviluppo:
```bash
npm run dev
```

## Funzionalità

- ✅ Autenticazione con AWS Cognito
- ✅ Gestione ruoli (SuperAdmin, Reseller, Admin, User)
- ✅ Cambio password obbligatorio al primo accesso
- 🚧 Dashboard SuperAdmin (in costruzione)
- 🚧 Dashboard Admin (in costruzione)
- 🚧 Dashboard User (in costruzione)

## TODO

- [ ] Completare SuperAdminDashboard con gestione Reseller e Tenant
- [ ] Completare AdminDashboard con gestione Utenti
- [ ] Completare UserDashboard con Profilo e Report
- [ ] Aggiungere modali per creazione/editing
- [ ] Aggiungere gestione errori globale
- [ ] Aggiungere loading states
- [ ] Aggiungere toast notifications
