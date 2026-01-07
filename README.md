# Speech-to-Text Multitenant Platform

Una piattaforma serverless completa ed enterprise-ready per la trascrizione automatica, l'analisi e la gestione di registrazioni audio in ambiente multitenant, con supporto per riassunti AI e analisi del sentiment.

## 📋 Indice

- [Panoramica](#-panoramica)
- [Parte Tecnica](#-parte-tecnica)
- [Security](#-security)
- [User Experience](#-user-experience)
- [Deploy](#-deploy)
- [Licenze e Funzionalità](#-licenze-e-funzionalità)
- [Monitoraggio e Manutenzione](#-monitoraggio-e-manutenzione)
- [Costi](#-costi)

---

## 🎯 Panoramica

**Speech-to-Text Multitenant** è una piattaforma cloud-native progettata per gestire la trascrizione automatica di conversazioni telefoniche con capacità avanzate di AI. Il sistema supporta organizzazioni, rivenditori (reseller) e clienti finali (tenant) con completo isolamento dei dati e gestione granulare dei permessi.

### Caratteristiche Principali

- ✅ **Trascrizione Automatica**: Conversione audio-to-text con identificazione speaker tramite Amazon Transcribe
- ✅ **Riassunti AI**: Generazione automatica di riassunti con Claude 3.5 Sonnet (Amazon Bedrock)
- ✅ **Analisi Sentiment**: Analisi emozionale delle conversazioni con Amazon Comprehend
- ✅ **Architettura Multitenant**: Supporto per reseller, tenant e utenti finali con isolamento dati
- ✅ **Vocabolari Personalizzati**: Supporto per terminologie specifiche per tenant
- ✅ **Dashboard Web**: Interfaccia amministrativa completa con React + Vite
- ✅ **Notifiche Email**: Invio automatico dei risultati in formato PDF
- ✅ **GDPR Compliant**: Crittografia, retention policy, eliminazione automatica dati
- ✅ **Serverless**: Architettura completamente serverless con costi ottimizzati

---

## 🏗️ Parte Tecnica

### Architettura

Il sistema utilizza un'architettura serverless moderna basata su AWS:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                       │
│                     AWS Amplify Hosting + Cognito                    │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      API Gateway (REST API)                          │
│             - Admin API (Cognito Authorizer)                         │
│             - Partner API (Custom Lambda Authorizer)                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   Lambda Functions       │    │   Storage & Database      │
│   - ProcessAudio         │    │   - S3 (audio files)      │
│   - GenerateSummary      │    │   - DynamoDB (metadata)   │
│   - SentimentAnalysis    │◄───┤   - Transcribe (jobs)     │
│   - SendEmail            │    │   - Bedrock (AI)          │
│   - TenantManagement     │    │   - Comprehend (NLP)      │
│   - UserManagement       │    │   - SES (email)           │
│   - LicenseManagement    │    │   - Cognito (auth)        │
│   - VocabularyMgmt       │    └──────────────────────────┘
└──────────────────────────┘
```

### Stack Tecnologico

#### Backend
- **Runtime**: Node.js 16.x
- **IaC**: AWS SAM (Serverless Application Model)
- **Language**: JavaScript (AWS SDK v2)
- **Deployment**: CloudFormation

#### Frontend
- **Framework**: React 18.3
- **Build Tool**: Vite 5.4
- **Auth**: AWS Amplify 6.15
- **Hosting**: AWS Amplify Console

#### Servizi AWS

| Servizio | Utilizzo | Note |
|----------|----------|------|
| **Lambda** | Elaborazione serverless | 13 funzioni principali |
| **API Gateway** | REST API | 2 API Gateway (Admin + Partner) |
| **DynamoDB** | Database NoSQL | 6 tabelle (records, licenses, tenants, resellers, vocabularies, partners) |
| **S3** | Storage oggetti | Audio files, PDF, vocabolari |
| **Transcribe** | Speech-to-Text | Supporto speaker labels, vocabolari custom |
| **Bedrock** | AI Generativa | Claude 3.5 Sonnet per riassunti |
| **Comprehend** | NLP | Sentiment analysis, language detection |
| **Cognito** | Autenticazione | User Pool per admin, reseller, user |
| **SES** | Email | Notifiche automatiche con PDF allegati |
| **EventBridge** | Scheduling | Cleanup giornaliero automatico |
| **VPC (Optional)** | Networking | Isolamento rete con NAT Gateway |
| **CloudWatch** | Monitoring | Logs e metriche |

### Lambda Functions

#### 1. **ProcessAudioFunction**
- **Trigger**: S3 Event (upload file .wav)
- **Funzione**: Orchestrazione principale del flusso di trascrizione
- **Workflow**:
  1. Legge metadata JSON associato al file audio (se disponibile)
  2. Estrae informazioni cliente/agente
  3. Verifica/crea licenza automaticamente per nuovi clienti
  4. Crea record in DynamoDB
  5. Avvia job Amazon Transcribe (con vocabolario custom se disponibile)
  6. Polling asincrono dello stato del job
  7. Quando completato, invoca le funzioni downstream (summary, sentiment, email)
- **Timeout**: 900s (15 minuti)

#### 2. **GenerateSummaryFunction**
- **Trigger**: Invocazione da ProcessAudio
- **Funzione**: Genera riassunto intelligente della conversazione
- **AI**: Amazon Bedrock con Claude 3.5 Sonnet
- **Output**: Riassunto 150-200 parole in italiano

#### 3. **SentimentAnalysisFunction**
- **Trigger**: Invocazione da ProcessAudio
- **Funzione**: Analizza il sentiment della conversazione
- **AI**: Amazon Comprehend
- **Output**: 
  - Sentiment complessivo (POSITIVE, NEGATIVE, NEUTRAL, MIXED)
  - Score granulari per segmenti temporali

#### 4. **SendEmailFunction**
- **Trigger**: Invocazione da ProcessAudio
- **Funzione**: Genera PDF e invia email con risultati
- **Componenti**:
  - Generazione PDF con `pdfkit` (trascrizione + riassunto + sentiment)
  - Upload PDF su S3
  - Invio email via SES con PDF allegato
  - URL firmato per download audio originale

#### 5. **TenantManagementFunction**
- **API**: `/api/tenants` (GET, POST, PUT, DELETE)
- **Funzione**: CRUD tenants con supporto reseller
- **Features**:
  - Creazione tenant con admin automatico in Cognito
  - Associazione/disassociazione reseller (organizzazioni o utenti indipendenti)
  - Supporto array multipli di reseller per tenant
  - Filtering basato su ruolo (superadmin vede tutti, reseller solo i propri)

#### 6. **UserManagementFunction**
- **API**: `/api/users` (GET, POST, PUT, DELETE)
- **Funzione**: Gestione utenti Cognito
- **Features**:
  - Creazione utenti con ruoli (superadmin, reseller, admin, user)
  - Assegnazione tenant/reseller
  - Update email e attributi custom
  - Filtering basato su permessi

#### 7. **LicenseManagementFunction**
- **API**: `/api/licenses` (GET, PUT)
- **Funzione**: Gestione licenze clienti
- **Tipi Licenza**: BASE, R (Riassunti), S (Sentiment), R+S (Completa)

#### 8. **VocabularyManagementFunction**
- **API**: `/api/vocabularies` (GET, POST, PUT, DELETE)
- **Funzione**: Gestione vocabolari personalizzati per Transcribe
- **Features**:
  - Upload file vocabolario su S3
  - Creazione/update vocabolari Transcribe
  - Associazione tenant-specifica

#### 9. **ResellerManagementFunction**
- **API**: `/api/resellers` (GET, POST, PUT, DELETE)
- **Funzione**: CRUD organizzazioni reseller

#### 10. **GetStatisticsFunction**
- **API**: `/api/statistics` (GET)
- **Funzione**: Statistiche aggregate
- **Metriche**: Totale registrazioni, durata, sentiment breakdown, per tenant

#### 11. **GetRecordingsFunction**
- **API**: `/api/recordings` (GET)
- **Funzione**: Lista registrazioni con filtering
- **Features**: Paginazione, filtering per tenant, URL firmati per download

#### 12. **GetUploadUrlFunction**
- **API**: `/upload-url` (POST)
- **Funzione**: Genera pre-signed URL per upload S3
- **Auth**: Custom Lambda Authorizer (API key partner)

#### 13. **CleanupFunction**
- **Trigger**: EventBridge (cron: ogni giorno alle 01:00 UTC)
- **Funzione**: Eliminazione automatica dati scaduti (TTL + S3 cleanup)

#### 14. **AuthorizerFunction**
- **Tipo**: Custom Lambda Authorizer
- **Funzione**: Validazione API key partner per Partner API
- **Verifica**: Query DynamoDB PartnersTable

#### 15. **CheckLicenseFunction**
- **Trigger**: Chiamata interna
- **Funzione**: Verifica tipo licenza per determinare elaborazioni da eseguire

### Database Schema (DynamoDB)

#### TranscriptionTable
```javascript
{
  recordId: "setera-{orkUid}",           // PK
  clientId: "setera-client123",
  agentId: "john-doe",
  timestamp: 1704067200,
  filename: "recording.wav",
  s3Path: "uploads/recording.wav",
  pdfS3Path: "recordings/{recordId}/transcript.pdf",
  status: "COMPLETED",
  transcription: "...",                  // Con speaker labels
  cleanTranscription: "...",             // Senza labels
  summary: "...",                        // Da Bedrock
  sentimentAnalysis: {                   // Da Comprehend
    overall: {...},
    temporal: [...]
  },
  licenseType: "R+S",
  fileSize: 2048000,
  ttl: 1706745600,                       // Auto-delete dopo 30 giorni
  
  // Metadata Setera (se disponibili)
  callId: "12345",
  callTimestamp: "2024-01-01T10:00:00Z",
  callDuration: 180,
  localParty: "0039...",
  remoteParty: "0039...",
  direction: "INBOUND",
  orkUid: "uid-123",
  tapeId: "tape-456",
  
  // GSI: AgentIndex (agentId + timestamp)
}
```

#### LicenseTable
```javascript
{
  clientId: "setera-client123",          // PK
  licenseType: "R+S",                    // BASE, R, S, R+S
  isActive: true,
  userEmail: "user@example.com",
  agentEmails: {
    "agent1": "agent1@example.com",
    ...
  },
  expirationDate: 1735689600,            // Optional
  autoCreated: true,                     // Flag per licenze auto-generate
  Name: "Company Name"
}
```

#### TenantsTable
```javascript
{
  tenantId: "company-abc",               // PK
  name: "Company ABC",
  description: "...",
  isActive: true,
  adminEmail: "admin@company.com",
  resellerIds: ["reseller-org-1", "reseller-org-2"],  // Array organizzazioni
  resellerUsers: ["reseller-user-sub-1"],             // Array utenti indipendenti
  createdAt: 1704067200,
  createdBy: "superadmin@platform.com"
  
  // GSI: ResellerIndex (resellerId)
}
```

#### ResellersTable
```javascript
{
  resellerId: "reseller-org-1",          // PK
  name: "Reseller Company",
  contactEmail: "contact@reseller.com",
  isActive: true,
  createdAt: 1704067200
}
```

#### CustomVocabulariesTable
```javascript
{
  vocabularyId: "uuid",                  // PK
  tenantId: "company-abc",
  vocabularyName: "transcribe-vocab-name",
  s3Path: "vocabularies/{tenantId}/{vocabularyId}.txt",
  status: "READY",                       // PENDING, READY, FAILED
  languageCode: "it-IT",
  createdAt: 1704067200
  
  // GSI: TenantIndex (tenantId)
}
```

#### PartnersTable
```javascript
{
  partnerId: "partner-setera",           // PK
  partnerName: "Setera PBX",
  apiKey: "hex-encoded-key",
  isActive: true,
  createdAt: 1704067200
  
  // GSI: ApiKeyIndex (apiKey)
}
```

### Flusso di Elaborazione

```
1. File WAV caricato su S3 (+ JSON metadata opzionale)
                ↓
2. ProcessAudioFunction triggata da S3 Event
                ↓
3. Lettura metadata, verifica/creazione licenza
                ↓
4. Creazione record DynamoDB (status: PROCESSING)
                ↓
5. Avvio Amazon Transcribe Job (con vocab custom se disponibile)
                ↓
6. Polling stato job (ogni 30s)
                ↓
7. Job completato → Download risultati JSON
                ↓
8. Formattazione trascrizione con speaker labels
                ↓
9. Aggiornamento DynamoDB (status: TRANSCRIBED)
                ↓
        ┌───────┴───────┐
        ▼               ▼
10a. Summary       10b. Sentiment
    (Bedrock)          (Comprehend)
        │               │
        └───────┬───────┘
                ▼
11. Attesa 10s per completamento
                ↓
12. SendEmailFunction
    - Genera PDF (pdfkit)
    - Upload PDF su S3
    - Invia email SES con allegato
                ↓
13. Aggiornamento DynamoDB (emailSent: true)
                ↓
14. COMPLETATO
```

### VPC Configuration (Opzionale)

Il sistema supporta deployment in VPC per maggiore sicurezza:

- **VPC**: 10.0.0.0/16
- **Public Subnets**: 2 AZ (10.0.1.0/24, 10.0.2.0/24) per NAT Gateway
- **Private Subnets**: 2 AZ (10.0.10.0/24, 10.0.20.0/24) per Lambda
- **NAT Gateways**: 2 (alta disponibilità)
- **VPC Endpoints**: S3 e DynamoDB (gateway, gratuiti)
- **Security Group**: Lambda SG con regole HTTPS outbound

**Nota**: VPC è disabilitato di default per ridurre costi (EnableVpc=false).

---

## 🔒 Security

### Autenticazione e Autorizzazione

#### 1. **Amazon Cognito User Pool**
- **User Pool ID**: Centralizzato per tutti gli utenti (admin, reseller, user)
- **Attributi Custom**:
  - `custom:role`: superadmin | reseller | admin | user
  - `custom:tenantId`: Associazione tenant
  - `custom:resellerId`: Associazione organizzazione reseller
- **Password Policy**:
  - Lunghezza minima: 12 caratteri
  - Richiesti: uppercase, lowercase, numeri, simboli
- **Token Validity**:
  - Access Token: 60 minuti
  - ID Token: 60 minuti
  - Refresh Token: 30 giorni

#### 2. **Modello di Autorizzazione Gerarchico**

```
┌─────────────────────────────────────────────────┐
│            SUPERADMIN                           │
│  - Gestisce tutto                               │
│  - Crea/modifica tenant, reseller, utenti       │
│  - Context switching per visualizzare come      │
│    qualsiasi tenant                             │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌───────────────────┐   ┌───────────────────┐
│     RESELLER      │   │      TENANT       │
│  - Gestisce propri│   │   (Organizzazione)│
│    tenant         │   │                   │
│  - Crea utenti per│   └────────┬──────────┘
│    i propri tenant│            │
└─────────┬─────────┘            ▼
          │              ┌───────────────────┐
          └─────────────►│      ADMIN        │
                         │  - Gestisce utenti│
                         │    del proprio    │
                         │    tenant         │
                         │  - Visualizza dati│
                         │    del tenant     │
                         └─────────--────────┘
```

#### 3. **JWT Verification**
- **Libreria**: `jsonwebtoken` + `jwks-rsa`
- **JWKS Endpoint**: `https://cognito-idp.{region}.amazonaws.com/{userPoolId}/.well-known/jwks.json`
- **Verifica**:
  - Signature con chiave pubblica RSA
  - Issuer: Cognito User Pool
  - Audience: User Pool Client ID
  - Scadenza token

#### 4. **API Gateway Authorization**

**Admin API** (Cognito Authorizer):
```javascript
// Header richiesto
Authorization: Bearer {idToken}

// Opzionale per context switching superadmin
X-Tenant-Id: {tenantId}
```

**Partner API** (Custom Lambda Authorizer):
```javascript
// Header richiesto
Authorization: Bearer {apiKey}

// L'authorizer valida l'API key contro PartnersTable
```

#### 5. **Isolamento Dati (Row-Level Security)**

Ogni Lambda function implementa filtering basato su ruolo:

```javascript
// Esempio: GetRecordingsFunction
if (userInfo.role === 'user') {
  // Vede solo i propri record
  filter = { clientId: userInfo.tenantId, agentId: userInfo.email }
} else if (userInfo.role === 'admin') {
  // Vede tutti i record del proprio tenant
  filter = { clientId: userInfo.tenantId }
} else if (userInfo.role === 'reseller') {
  // Vede record dei tenant che gli appartengono
  const myTenants = await getResellerTenants(userInfo.sub)
  filter = { clientId: { $in: myTenants } }
} else if (userInfo.role === 'superadmin') {
  // Context switching: se specificato X-Tenant-Id, filtra per quel tenant
  const effectiveTenantId = headers['X-Tenant-Id'] || 'ALL'
  if (effectiveTenantId !== 'ALL') {
    filter = { clientId: effectiveTenantId }
  }
  // Altrimenti vede tutto
}
```

### Crittografia

#### 1. **Data at Rest**
- **DynamoDB**: SSE-KMS abilitato su tutte le tabelle
- **S3**: Server-Side Encryption (SSE-AES256) su tutti gli oggetti
- **Transcribe**: Output automaticamente crittografato da AWS

#### 2. **Data in Transit**
- **TLS 1.2+**: Obbligatorio per tutte le connessioni API Gateway
- **HTTPS**: Tutti gli endpoint esposti solo via HTTPS
- **Pre-signed URLs**: Expire dopo 7 giorni

### GDPR Compliance

#### 1. **Right to Erasure**
- **TTL DynamoDB**: Eliminazione automatica record dopo 30 giorni (configurabile)
- **S3 Lifecycle**: Eliminazione automatica file audio e PDF dopo 30 giorni
- **CleanupFunction**: Pulizia giornaliera per sincronizzare S3 e DynamoDB

#### 2. **Data Minimization**
- **Metadata limitati**: Solo dati necessari per il servizio
- **No PII non necessari**: Email e identificatori minimi

#### 3. **Right to Access**
- **API `/api/recordings`**: Utente può scaricare tutte le proprie registrazioni e PDF
- **Email automatica**: Copia dei dati inviata all'utente appena disponibile

#### 4. **Consent Management**
- **Licenze**: Sistema di licenze che abilita/disabilita funzionalità
- **isActive flag**: Disattivazione immediata elaborazioni

#### 5. **Data Residency**
- **Region**: `eu-central-1` (Francoforte) per compliance europea
- **Tutti i dati**: Rimangono all'interno della region EU

### Logging e Audit

- **CloudWatch Logs**: Tutti i log Lambda con retention configurabile
- **No Sensitive Data in Logs**: Password, API keys, contenuti audio mai loggati
- **Audit Trail**: Timestamp e userEmail in tutti i record DynamoDB per tracking modifiche

### IAM e Least Privilege

Ogni Lambda ha un ruolo IAM dedicato con permessi minimi:

```yaml
# Esempio: ProcessAudioFunction
Policies:
  - S3ReadPolicy: { BucketName: audio-bucket }
  - DynamoDBCrudPolicy: { TableName: TranscriptionTable }
  - DynamoDBCrudPolicy: { TableName: LicenseTable }
  - DynamoDBReadPolicy: { TableName: VocabulariesTable }
  - Statement:
      - Effect: Allow
        Action: 
          - transcribe:StartTranscriptionJob
          - transcribe:GetTranscriptionJob
        Resource: '*'
      - Effect: Allow
        Action: lambda:InvokeFunction
        Resource: 
          - !GetAtt GenerateSummaryFunction.Arn
          - !GetAtt SentimentAnalysisFunction.Arn
          - !GetAtt SendEmailFunction.Arn
```

### Best Practices Implementate

- ✅ **Environment Variables**: Nessun secret hardcoded, tutto da variabili ambiente
- ✅ **Secrets Management**: API keys in DynamoDB (hashed), password temporanee Cognito
- ✅ **CORS**: Configurato correttamente con header specifici
- ✅ **Rate Limiting**: API Gateway throttling configurabile
- ✅ **Input Validation**: Tutti gli input validati prima dell'elaborazione
- ✅ **Error Handling**: Nessuna info sensibile negli errori esposti all'utente

---

## 🎨 User Experience

### Frontend Architecture

```
Deploy/frontend/
├── public/
│   ├── fonts/              # Poppins (Regular, Bold)
│   └── img/                # Logo (PNG, SVG)
├── src/
│   ├── components/
│   │   ├── AdminDashboard.jsx           # Dashboard admin/user
│   │   ├── AdminManagement.jsx          # Gestione admin (per superadmin)
│   │   ├── ResellersManagement.jsx      # CRUD reseller
│   │   ├── SelectContext.jsx            # Context switching superadmin/reseller
│   │   ├── SuperadminManagement.jsx     # Dashboard superadmin
│   │   ├── TenantsManagement.jsx        # CRUD tenant
│   │   ├── UserDashboard.jsx            # Dashboard utenti finali
│   │   └── UsersManagement.jsx          # CRUD utenti Cognito
│   ├── config/
│   │   └── amplify.js                   # Configurazione Amplify/Cognito
│   ├── utils/
│   │   ├── apiInterceptor.js            # Aggiunge X-Tenant-Id header automaticamente
│   │   ├── tenantContext.js             # Gestione context switching
│   │   └── translations.js              # Traduzioni IT/EN
│   ├── App.jsx                          # Main app con routing
│   ├── main.jsx                         # Entry point
│   └── index.css                        # Stili globali
├── vite.config.js
└── package.json
```

### Funzionalità per Ruolo

#### 👑 **SUPERADMIN**

**Dashboard:**
- Overview completo della piattaforma
- Statistiche aggregate di tutti i tenant
- Lista tenant con possibilità di context switching

**Gestione Tenant:**
- Creazione tenant (nome, descrizione, admin email/password)
- Associazione/disassociazione reseller (multipli)
- Modifica settings tenant
- Disattivazione/cancellazione tenant

**Gestione Reseller:**
- CRUD organizzazioni reseller
- Visualizzazione tenant associati

**Gestione Utenti:**
- Creazione utenti con qualsiasi ruolo
- Assegnazione tenant/reseller
- Modifica email, ruolo, tenant
- Cancellazione utenti
- Visualizzazione completa User Pool Cognito

**Context Switching:**
- Selezione tenant dal menu dropdown
- Visualizzazione dati come se fosse admin di quel tenant
- Indicatore visivo "Visualizzando come: {Tenant}"

**Gestione Licenze:**
- Visualizzazione tutte le licenze
- Modifica tipo licenza (BASE, R, S, R+S)
- Attivazione/disattivazione licenze

**Gestione Vocabolari:**
- Upload vocabolari custom per tenant
- Associazione vocabolario-tenant
- Monitoraggio stato Transcribe

#### 🏢 **RESELLER**

**Dashboard:**
- Statistiche aggregate dei propri tenant
- Lista tenant gestiti

**Gestione Tenant:**
- Creazione tenant (automaticamente associati al reseller)
- Modifica settings tenant propri
- Disattivazione tenant propri

**Gestione Utenti:**
- Creazione admin per i propri tenant
- Gestione utenti dei tenant propri
- No accesso a utenti di altri reseller

**Context Switching:**
- Selezione tra i propri tenant
- Visualizzazione dati specifici del tenant selezionato

**Gestione Licenze:**
- Visualizzazione licenze dei propri tenant
- Modifica tipo licenza per i propri tenant

#### 🔧 **ADMIN** (Tenant)

**Dashboard:**
- Statistiche del proprio tenant
- Lista registrazioni del tenant
- Filtri per sentiment, data, agente

**Visualizzazione Registrazioni:**
- Tabella paginata con:
  - Data/ora
  - Agente
  - Numero chiamato
  - Durata
  - Sentiment (badge colorato)
  - Azioni: Download audio, Download PDF
- Search box per filtrare
- Filtri per sentiment (ALL, POSITIVE, NEGATIVE, NEUTRAL, MIXED)

**Gestione Utenti:**
- Creazione utenti (role: user) per il proprio tenant
- Modifica email utenti del tenant
- Cancellazione utenti del tenant

**Gestione Licenze:**
- Visualizzazione licenza del proprio tenant
- Richiesta upgrade (via ticket, non self-service)

**Gestione Vocabolari:**
- Upload vocabolari custom per il tenant
- Gestione terminologie specifiche del dominio

### Componenti UI Principali

#### 1. **Login Page**
```jsx
- Email + Password
- "Accedi" button
- "Hai dimenticato la password?"
- Supporto new password required (primo login)
```

#### 2. **SelectContext Component**
```jsx
// Per superadmin e reseller
<select>
  <option value="">-- Tutti i tenant --</option>
  {tenants.map(t => (
    <option value={t.tenantId}>{t.name}</option>
  ))}
</select>

// Badge indicatore
{isViewingAsTenant && (
  <div class="context-indicator">
    👁️ Visualizzando come: {selectedTenant.name}
  </div>
)}
```

#### 3. **AdminDashboard Component**

**Sezione Statistiche:**
```jsx
<div className="stats-grid">
  <StatCard 
    title="Totale Registrazioni" 
    value={stats.totalRecordings}
    icon="🎙️"
  />
  <StatCard 
    title="Durata Totale" 
    value={formatDuration(stats.totalDuration)}
    icon="⏱️"
  />
  <StatCard 
    title="Sentiment Positivo" 
    value={`${stats.sentimentBreakdown.POSITIVE}%`}
    icon="😊"
    color="green"
  />
  <StatCard 
    title="Sentiment Negativo" 
    value={`${stats.sentimentBreakdown.NEGATIVE}%`}
    icon="😟"
    color="red"
  />
</div>
```

**Tabella Registrazioni:**
```jsx
<table>
  <thead>
    <tr>
      <th>Data/Ora</th>
      <th>Agente</th>
      <th>Numero</th>
      <th>Durata</th>
      <th>Sentiment</th>
      <th>Azioni</th>
    </tr>
  </thead>
  <tbody>
    {recordings.map(rec => (
      <tr>
        <td>{formatDate(rec.timestamp)}</td>
        <td>{rec.agentId}</td>
        <td>{rec.remoteParty || 'N/A'}</td>
        <td>{rec.callDuration}s</td>
        <td>
          <SentimentBadge sentiment={rec.sentiment} />
        </td>
        <td>
          <button onClick={() => downloadRecording(rec.audioUrl)}>
            🎵 Audio
          </button>
          {rec.pdfUrl && (
            <button onClick={() => downloadRecording(rec.pdfUrl)}>
              📄 PDF
            </button>
          )}
        </td>
      </tr>
    ))}
  </tbody>
</table>
```

#### 4. **TenantsManagement Component**
```jsx
// Lista tenant
<div className="tenant-card">
  <h3>{tenant.name}</h3>
  <p>{tenant.description}</p>
  <div className="tenant-info">
    <span>Admin: {tenant.adminEmail}</span>
    <span>Status: {tenant.isActive ? '✅ Attivo' : '❌ Inattivo'}</span>
    {tenant.resellerOrganizations?.map(r => (
      <span>Reseller: {r.name}</span>
    ))}
  </div>
  <div className="actions">
    <button onClick={() => editTenant(tenant)}>✏️ Modifica</button>
    <button onClick={() => associateReseller(tenant)}>🔗 Associa Reseller</button>
    <button onClick={() => deleteTenant(tenant)}>🗑️ Elimina</button>
  </div>
</div>

// Modal creazione
<Modal open={showCreateModal}>
  <form onSubmit={handleCreate}>
    <input name="name" placeholder="Nome tenant" required />
    <textarea name="description" placeholder="Descrizione" />
    <input name="adminEmail" type="email" placeholder="Email admin" required />
    <input name="adminPassword" type="password" placeholder="Password temporanea" required />
    <select name="resellerId">
      <option value="">-- Nessun reseller --</option>
      {resellers.map(r => (
        <option value={r.resellerId}>{r.name}</option>
      ))}
    </select>
    <button type="submit">Crea Tenant</button>
  </form>
</Modal>
```

#### 5. **UsersManagement Component**
```jsx
// Tabella utenti
<table>
  <thead>
    <tr>
      <th>Email</th>
      <th>Ruolo</th>
      <th>Tenant</th>
      <th>Reseller</th>
      <th>Status</th>
      <th>Azioni</th>
    </tr>
  </thead>
  <tbody>
    {users.map(user => (
      <tr>
        <td>{user.email}</td>
        <td><RoleBadge role={user.role} /></td>
        <td>{user.tenantName || 'N/A'}</td>
        <td>{user.resellerName || 'N/A'}</td>
        <td>{user.status}</td>
        <td>
          <button onClick={() => editUser(user)}>✏️</button>
          <button onClick={() => deleteUser(user)}>🗑️</button>
        </td>
      </tr>
    ))}
  </tbody>
</table>
```

### Design System

**Palette Colori:**
- Primary: `#2563eb` (Blue)
- Success: `#10b981` (Green)
- Warning: `#f59e0b` (Orange)
- Danger: `#ef4444` (Red)
- Neutral: `#6b7280` (Gray)

**Tipografia:**
- Font: Poppins (Regular: 400, Bold: 700)
- Headings: Poppins Bold
- Body: Poppins Regular

**Sentiment Badges:**
```jsx
const sentimentColors = {
  POSITIVE: { bg: '#d1fae5', text: '#065f46', emoji: '😊' },
  NEGATIVE: { bg: '#fee2e2', text: '#991b1b', emoji: '😟' },
  NEUTRAL: { bg: '#e5e7eb', text: '#374151', emoji: '😐' },
  MIXED: { bg: '#fef3c7', text: '#92400e', emoji: '🤔' }
}
```

### Responsive Design

- **Desktop**: Layout a griglia, sidebar navigation
- **Tablet**: Layout adattivo, sidebar collassabile
- **Mobile**: Stack verticale, menu hamburger

### Accessibilità (A11Y)

- ✅ Semantic HTML (button, nav, main, section)
- ✅ ARIA labels su icone e azioni
- ✅ Contrast ratio conforme WCAG AA
- ✅ Keyboard navigation
- ✅ Focus visible

---

## 🚀 Deploy

### Prerequisiti

#### Software Richiesto
```bash
# AWS CLI
aws --version  # >= 2.x

# AWS SAM CLI
sam --version  # >= 1.x

# Node.js
node --version  # >= 16.x
npm --version   # >= 8.x
```

#### Configurazione AWS

##### 1. **Configurazione Profilo AWS**
```bash
# Lista profili esistenti
aws configure list-profiles

# Imposta profilo per la sessione (Windows CMD)
set AWS_PROFILE=nome-profilo

# Imposta profilo per la sessione (Linux/Mac)
export AWS_PROFILE=nome-profilo

# Verifica identità
aws sts get-caller-identity
```

##### 2. **Configurazione AWS SSO (se applicabile)**
```bash
# Prima volta: configura SSO
aws configure sso

# Login con SSO
aws sso login --profile nome-profilo
```

##### 3. **Verifica Regione**
```bash
# Il progetto usa eu-central-1 (Francoforte) di default
aws configure get region --profile nome-profilo
# Output atteso: eu-central-1
```

### Deploy Backend (AWS SAM)

#### 1. **Preparazione**

```bash
# Naviga alla directory Deploy
cd Deploy

# Installa dipendenze Lambda (se modificato package.json)
cd src/{lambda-function}
npm install
cd ../..
```

#### 2. **Build**

```bash
# Build con SAM
sam build

# Oppure build con container (per dipendenze native)
sam build --use-container
```

**Output atteso:**
```
Build Succeeded

Built Artifacts  : .aws-sam/build
Built Template   : .aws-sam/build/template.yaml
```

#### 3. **Deploy Prima Volta (Guided)**

```bash
sam deploy --guided --profile nome-profilo
```

**Parametri richiesti:**

| Parametro | Valore | Descrizione |
|-----------|--------|-------------|
| **Stack Name** | `speech-to-text-multitenant` | Nome dello stack CloudFormation |
| **AWS Region** | `eu-central-1` | Regione di deploy |
| **Environment** | `dev` o `prod` | Ambiente |
| **RetentionDays** | `30` | Giorni di retention dati |
| **EnableVpc** | `false` | Abilita VPC (false per ridurre costi) |
| **ProjectName** | `ProjectSTT` | Tag per cost tracking |
| **Confirm changes** | `Y` | Conferma changeset |
| **Allow SAM CLI IAM role creation** | `Y` | Permetti creazione ruoli IAM |
| **Save arguments to config** | `Y` | Salva config in samconfig.toml |

#### 4. **Deploy Successivi**

```bash
# Deploy senza guided (usa samconfig.toml)
sam deploy --profile nome-profilo
```

#### 5. **Verifica Deploy**

```bash
# Lista stack
aws cloudformation describe-stacks \
  --stack-name speech-to-text-multitenant \
  --query 'Stacks[0].StackStatus' \
  --profile nome-profilo

# Output atteso: "CREATE_COMPLETE" o "UPDATE_COMPLETE"

# Ottieni outputs (API endpoints, etc)
aws cloudformation describe-stacks \
  --stack-name speech-to-text-multitenant \
  --query 'Stacks[0].Outputs' \
  --profile nome-profilo
```

**Outputs importanti:**
```json
[
  {
    "OutputKey": "AdminApiEndpoint",
    "OutputValue": "https://xxx.execute-api.eu-central-1.amazonaws.com/dev"
  },
  {
    "OutputKey": "ApiEndpoint",
    "OutputValue": "https://yyy.execute-api.eu-central-1.amazonaws.com/dev"
  },
  {
    "OutputKey": "CognitoUserPoolId",
    "OutputValue": "eu-central-1_XXXXXXXXX"
  },
  {
    "OutputKey": "CognitoUserPoolClientId",
    "OutputValue": "xxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
]
```

### Deploy Frontend (AWS Amplify)

#### 1. **Configurazione Amplify**

Aggiorna `Deploy/frontend/src/config/amplify.js` con gli outputs dello stack:

```javascript
export const amplifyConfig = { 
  Auth: { 
    Cognito: { 
      userPoolId: 'eu-central-1_XXXXXXXXX',      // Da CloudFormation Output
      userPoolClientId: 'xxxxxxxxxxxxxxxxxx',    // Da CloudFormation Output
      region: 'eu-central-1', 
      signUpVerificationMethod: 'code', 
      loginWith: { 
        email: true, 
      }, 
    } 
  } 
}; 
```

#### 2. **Build Locale (Test)**

```bash
cd Deploy/frontend

# Installa dipendenze
npm ci

# Build
npm run build

# Test locale
npm run dev
# Apri http://localhost:5173
```

#### 3. **Deploy su AWS Amplify Console**

**Opzione A: Connessione GitHub/GitLab (CI/CD automatico)**

1. Accedi a [AWS Amplify Console](https://console.aws.amazon.com/amplify/)
2. Click "New app" → "Host web app"
3. Connetti repository GitHub/GitLab
4. Seleziona repository e branch
5. Configura build settings:
   - Build command: `npm ci && npm run build`
   - Base directory: `Deploy/frontend`
   - Artifacts baseDirectory: `dist`
6. Click "Save and deploy"

**Opzione B: Deploy Manuale**

```bash
cd Deploy/frontend

# Installa Amplify CLI
npm install -g @aws-amplify/cli

# Inizializza Amplify
amplify init

# Configura hosting
amplify add hosting

# Publish
amplify publish
```

**Opzione C: S3 + CloudFront (Alternativa)**

```bash
# Build
npm run build

# Carica su S3
aws s3 sync dist/ s3://nome-bucket-frontend/ --profile nome-profilo

# Crea CloudFront distribution manualmente nella console
# Configura origin = S3 bucket, default root object = index.html
```

#### 4. **Verifica Frontend**

- Accedi all'URL Amplify (es. `https://main.xxx.amplifyapp.com`)
- Verifica login con Cognito
- Controlla DevTools per errori API

### Post-Deploy Configuration

#### 1. **Crea Utente Superadmin Iniziale**

```bash
# Via AWS Console Cognito o AWS CLI
aws cognito-idp admin-create-user \
  --user-pool-id eu-central-1_XXXXXXXXX \
  --username superadmin@yourdomain.com \
  --user-attributes \
    Name=email,Value=superadmin@yourdomain.com \
    Name=email_verified,Value=true \
    Name=custom:role,Value=superadmin \
  --temporary-password "TempPassword123!" \
  --message-action SUPPRESS \
  --profile nome-profilo

# Imposta password permanente
aws cognito-idp admin-set-user-password \
  --user-pool-id eu-central-1_XXXXXXXXX \
  --username superadmin@yourdomain.com \
  --password "YourSecurePassword123!" \
  --permanent \
  --profile nome-profilo
```

#### 2. **Configura Amazon SES per Email**

```bash
# Verifica dominio email
aws ses verify-domain-identity \
  --domain yourdomain.com \
  --region eu-central-1 \
  --profile nome-profilo

# Oppure verifica singola email (per test)
aws ses verify-email-identity \
  --email-address noreply@yourdomain.com \
  --region eu-central-1 \
  --profile nome-profilo

# Controlla stato verifica
aws ses get-identity-verification-attributes \
  --identities yourdomain.com \
  --region eu-central-1 \
  --profile nome-profilo

# Richiedi uscita da sandbox (per produzione)
# Vai su AWS Console > SES > Account Dashboard > Request production access
```

#### 3. **Configura S3 Bucket per Audio Files**

**Nota**: Il bucket è hardcoded come `speech-to-text-audio-960902921831-dev` nel template.yaml. 

**Opzione 1**: Usa bucket esistente (se già presente)

**Opzione 2**: Crea nuovo bucket e aggiorna template.yaml

```bash
# Crea bucket
aws s3 mb s3://speech-to-text-audio-{AccountId}-{Environment} \
  --region eu-central-1 \
  --profile nome-profilo

# Abilita crittografia
aws s3api put-bucket-encryption \
  --bucket speech-to-text-audio-{AccountId}-{Environment} \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }' \
  --profile nome-profilo

# Configura CORS
aws s3api put-bucket-cors \
  --bucket speech-to-text-audio-{AccountId}-{Environment} \
  --cors-configuration file://cors-config.json \
  --profile nome-profilo

# cors-config.json
{
  "CORSRules": [{
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }]
}

# Configura Lifecycle (auto-delete dopo 30 giorni)
aws s3api put-bucket-lifecycle-configuration \
  --bucket speech-to-text-audio-{AccountId}-{Environment} \
  --lifecycle-configuration file://lifecycle-config.json \
  --profile nome-profilo

# lifecycle-config.json
{
  "Rules": [{
    "Id": "DeleteAfter30Days",
    "Status": "Enabled",
    "ExpirationInDays": 30
  }]
}
```

**Aggiorna template.yaml** con il nome del bucket effettivo:
```yaml
# Cerca e sostituisci tutte le occorrenze di:
speech-to-text-audio-960902921831-dev
# Con:
speech-to-text-audio-{AccountId}-{Environment}
```

#### 4. **Abilita Bedrock Model Access (Claude)**

```bash
# Vai su AWS Console > Bedrock > Model access
# Richiedi accesso a "Claude 3.5 Sonnet"
# Region: eu-central-1

# Verifica accesso via CLI
aws bedrock list-foundation-models \
  --region eu-central-1 \
  --profile nome-profilo \
  --query 'modelSummaries[?contains(modelId, `anthropic.claude-3-5-sonnet`)]'
```

#### 5. **Configura S3 Event Notification**

```bash
# Abilita notifica S3 → Lambda per ProcessAudioFunction
aws s3api put-bucket-notification-configuration \
  --bucket speech-to-text-audio-{AccountId}-{Environment} \
  --notification-configuration file://s3-notification.json \
  --profile nome-profilo

# s3-notification.json
{
  "LambdaFunctionConfigurations": [{
    "Id": "ProcessAudioOnUpload",
    "LambdaFunctionArn": "arn:aws:lambda:eu-central-1:{AccountId}:function:speech-to-text-multitenant-ProcessAudio-dev",
    "Events": ["s3:ObjectCreated:*"],
    "Filter": {
      "Key": {
        "FilterRules": [{
          "Name": "suffix",
          "Value": ".wav"
        }]
      }
    }
  }]
}

# Aggiungi permesso Lambda per S3
aws lambda add-permission \
  --function-name speech-to-text-multitenant-ProcessAudio-dev \
  --statement-id s3-invoke-permission \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::speech-to-text-audio-{AccountId}-{Environment} \
  --profile nome-profilo
```

**Nota**: Questo step potrebbe essere necessario solo se il bucket non è gestito da SAM/CloudFormation.

#### 6. **Test End-to-End**

```bash
# 1. Login frontend con superadmin
# 2. Crea un tenant di test
# 3. Crea una licenza per il tenant
# 4. Upload file audio di test su S3

aws s3 cp test_audio.wav s3://speech-to-text-audio-{AccountId}-{Environment}/test_audio.wav \
  --profile nome-profilo

# 5. Monitora CloudWatch Logs per ProcessAudioFunction
aws logs tail /aws/lambda/speech-to-text-multitenant-ProcessAudio-dev \
  --follow \
  --profile nome-profilo

# 6. Verifica record creato in DynamoDB
aws dynamodb scan \
  --table-name speech-to-text-records-dev \
  --limit 1 \
  --profile nome-profilo

# 7. Controlla email inviata
# 8. Verifica PDF generato in S3
```

### Troubleshooting Deploy

#### Problema: "Template format error"
```bash
# Valida template
sam validate --profile nome-profilo

# Controlla sintassi YAML
yamllint template.yaml
```

#### Problema: "Insufficient permissions"
```bash
# Verifica permessi IAM dell'utente/role
aws iam get-user --profile nome-profilo
aws iam list-attached-user-policies --user-name {UserName} --profile nome-profilo

# Permessi richiesti: CloudFormation, Lambda, IAM, S3, DynamoDB, API Gateway, Cognito
```

#### Problema: "Lambda in VPC has no internet access"
```bash
# Se EnableVpc=true, verifica NAT Gateway
aws ec2 describe-nat-gateways \
  --filter "Name=vpc-id,Values={VpcId}" \
  --profile nome-profilo

# Verifica route tables
aws ec2 describe-route-tables \
  --filter "Name=vpc-id,Values={VpcId}" \
  --profile nome-profilo
```

#### Problema: "Transcribe job fails"
```bash
# Controlla permessi Lambda su Transcribe
aws iam get-policy-version \
  --policy-arn {ProcessAudioFunctionRoleArn} \
  --version-id v1 \
  --profile nome-profilo

# Verifica quota Transcribe
aws service-quotas get-service-quota \
  --service-code transcribe \
  --quota-code L-1234ABCD \
  --region eu-central-1 \
  --profile nome-profilo
```

#### Problema: "Email not sent"
```bash
# Verifica identità SES
aws ses get-identity-verification-attributes \
  --identities noreply@yourdomain.com \
  --region eu-central-1 \
  --profile nome-profilo

# Controlla se ancora in sandbox
aws sesv2 get-account \
  --region eu-central-1 \
  --profile nome-profilo \
  --query 'ProductionAccessEnabled'

# Se false, solo email verificate ricevono notifiche (sandbox mode)
```

#### Problema: "Frontend 401 Unauthorized"
```bash
# Verifica configurazione Cognito in amplify.js
# Controlla token JWT nel browser DevTools > Application > Local Storage

# Testa API manualmente
TOKEN=$(aws cognito-idp admin-initiate-auth \
  --user-pool-id eu-central-1_XXXXXXXXX \
  --client-id xxxxxxxxxxxxxxxxxx \
  --auth-flow ADMIN_NO_SRP_AUTH \
  --auth-parameters USERNAME=test@example.com,PASSWORD=Password123! \
  --profile nome-profilo \
  --query 'AuthenticationResult.IdToken' \
  --output text)

curl -H "Authorization: Bearer $TOKEN" \
  https://xxx.execute-api.eu-central-1.amazonaws.com/dev/api/statistics
```

### Rollback e Cleanup

#### Rollback Deploy
```bash
# CloudFormation rollback automatico in caso di errore
# Per rollback manuale a versione precedente:
aws cloudformation update-stack \
  --stack-name speech-to-text-multitenant \
  --use-previous-template \
  --profile nome-profilo
```

#### Eliminazione Stack Completa
```bash
# ⚠️ ATTENZIONE: Elimina TUTTI i dati!

# Svuota bucket S3 prima (se non ha retention policy)
aws s3 rm s3://speech-to-text-audio-{AccountId}-{Environment}/ --recursive --profile nome-profilo

# Elimina stack CloudFormation
aws cloudformation delete-stack \
  --stack-name speech-to-text-multitenant \
  --profile nome-profilo

# Monitora eliminazione
aws cloudformation wait stack-delete-complete \
  --stack-name speech-to-text-multitenant \
  --profile nome-profilo

# Elimina Amplify app (se usato)
aws amplify delete-app --app-id {AppId} --profile nome-profilo
```

---

## 📝 Licenze e Funzionalità

### Tipi di Licenza

| Licenza | Descrizione | Funzionalità Abilitate |
|---------|-------------|------------------------|
| **BASE** | Trascrizione base | ✅ Trascrizione audio<br>✅ Speaker labels<br>✅ Email notifica |
| **R** | Riassunti | ✅ BASE +<br>✅ Riassunto AI (Claude) |
| **S** | Sentiment | ✅ BASE +<br>✅ Analisi sentiment (Comprehend) |
| **R+S** | Completa | ✅ Tutte le funzionalità |

### Gestione Licenze

#### Creazione Automatica
Quando un nuovo `clientId` carica un file audio, il sistema:
1. Verifica se esiste licenza in `LicenseTable`
2. Se non esiste, crea automaticamente licenza `R+S` (completa)
3. Crea utente Cognito automaticamente con password temporanea `Password.1234!`
4. L'utente deve cambiare password al primo login

#### Upgrade/Downgrade
Solo **superadmin** può modificare tipo licenza:
- Dashboard → Gestione Licenze → Seleziona cliente → Modifica tipo

#### Disattivazione
Impostare `isActive: false` su licenza:
- Blocca nuove elaborazioni
- Non elimina dati esistenti

---

## 📊 Monitoraggio e Manutenzione

### CloudWatch Logs

```bash
# Tail logs in tempo reale
aws logs tail /aws/lambda/{FunctionName} --follow --profile nome-profilo

# Query logs (Insights)
aws logs start-query \
  --log-group-name /aws/lambda/speech-to-text-multitenant-ProcessAudio-dev \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/' \
  --profile nome-profilo
```

### Metriche CloudWatch

**Lambda Metrics**:
- `Invocations`: Numero di invocazioni
- `Errors`: Errori non gestiti
- `Duration`: Tempo di esecuzione
- `Throttles`: Richieste throttled

**API Gateway Metrics**:
- `Count`: Numero richieste
- `4XXError`: Errori client
- `5XXError`: Errori server
- `Latency`: Latenza

**DynamoDB Metrics**:
- `ConsumedReadCapacityUnits`: RCU consumate
- `ConsumedWriteCapacityUnits`: WCU consumate
- `SystemErrors`: Errori di sistema

### Allarmi CloudWatch (Consigliati)

```bash
# Esempio: Allarme su errori Lambda
aws cloudwatch put-metric-alarm \
  --alarm-name "STT-ProcessAudio-Errors" \
  --alarm-description "Allarme se ProcessAudio ha > 5 errori in 5 minuti" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=speech-to-text-multitenant-ProcessAudio-dev \
  --evaluation-periods 1 \
  --alarm-actions arn:aws:sns:eu-central-1:{AccountId}:alert-topic \
  --profile nome-profilo
```

### Backup e Disaster Recovery

#### DynamoDB
- **Point-in-Time Recovery (PITR)**: Abilita per backup continui
  ```bash
  aws dynamodb update-continuous-backups \
    --table-name speech-to-text-records-dev \
    --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true \
    --profile nome-profilo
  ```
- **On-Demand Backups**: Backup manuali prima di manutenzioni
  ```bash
  aws dynamodb create-backup \
    --table-name speech-to-text-records-dev \
    --backup-name "backup-$(date +%Y%m%d-%H%M%S)" \
    --profile nome-profilo
  ```

#### S3
- **Versioning**: Abilita per recovery accidentale
  ```bash
  aws s3api put-bucket-versioning \
    --bucket speech-to-text-audio-{AccountId}-{Environment} \
    --versioning-configuration Status=Enabled \
    --profile nome-profilo
  ```
- **Cross-Region Replication**: Per DR geografico
- **S3 Lifecycle**: Transition a Glacier dopo 30 giorni per archivio economico

### Manutenzione Programmata

#### Pulizia Manuale Dati Scaduti
```bash
# Se CleanupFunction non funziona, pulizia manuale
aws dynamodb scan \
  --table-name speech-to-text-records-dev \
  --filter-expression "ttl < :now" \
  --expression-attribute-values '{":now": {"N": "'$(date +%s)'"}}' \
  --projection-expression recordId \
  --profile nome-profilo \
  | jq -r '.Items[].recordId.S' \
  | while read recordId; do
      aws dynamodb delete-item \
        --table-name speech-to-text-records-dev \
        --key "{\"recordId\": {\"S\": \"$recordId\"}}" \
        --profile nome-profilo
    done
```

#### Aggiornamento Lambda Runtime
```bash
# Quando Node.js 16 diventa deprecato
# 1. Testa localmente con nuova versione
# 2. Aggiorna template.yaml:
#    Runtime: nodejs18.x (o nodejs20.x)
# 3. sam build && sam deploy
```

#### Rotazione Secret/API Keys
```bash
# Genera nuova API key per partner
NEW_API_KEY=$(openssl rand -hex 32)

# Aggiorna DynamoDB
aws dynamodb update-item \
  --table-name speech-to-text-partners-dev \
  --key '{"partnerId": {"S": "partner-setera"}}' \
  --update-expression "SET apiKey = :newKey" \
  --expression-attribute-values "{\":newKey\": {\"S\": \"$NEW_API_KEY\"}}" \
  --profile nome-profilo

echo "Nuova API Key: $NEW_API_KEY"
# Comunica al partner per aggiornare integrazione
```

---

## 💰 Costi

### Stima Mensile (Uso Moderato)

Scenario: 500 registrazioni/mese, 3 min/registrazione, licenza R+S

| Servizio | Utilizzo | Costo Unitario | Costo Mensile |
|----------|----------|----------------|---------------|
| **Lambda** | 500 invocazioni × 13 funzioni × 30s avg<br>= 195.000 request-secondi<br>Memory: 256 MB | First 1M requests free<br>$0.0000166667 per GB-second | **$5** |
| **API Gateway** | 500 upload + 1000 admin calls<br>= 1.500 requests | First 1M requests free | **$0** (free tier) |
| **S3** | 500 × 15 MB (audio + PDF)<br>= 7.5 GB storage<br>1500 GET/PUT requests | $0.023/GB/month<br>$0.005/1000 PUT<br>$0.0004/1000 GET | **$0.17** |
| **DynamoDB** | PAY_PER_REQUEST<br>500 writes + 1500 reads/month | $1.25/million writes<br>$0.25/million reads | **$0.001** |
| **Transcribe** | 500 × 3 min = 1.500 minuti | $0.024/min (first 250.000 min) | **$36** |
| **Bedrock (Claude)** | 500 riassunti<br>Avg 1000 input tokens + 300 output | $3/M input tokens<br>$15/M output tokens | **$3.75** |
| **Comprehend** | 500 sentiment analysis<br>Avg 500 chars | $0.0001/100 chars | **$0.25** |
| **SES** | 500 email con PDF allegato | $0.10/1000 email | **$0.05** |
| **Cognito** | 100 utenti attivi | First 50.000 MAU free | **$0** (free tier) |
| **CloudWatch** | 5 GB logs/month | $0.50/GB | **$2.50** |
| **NAT Gateway** (se VPC abilitato) | 744 ore × 1 GB data/ora | $0.045/hour + $0.045/GB | **❌ $67** (disabilitato di default) |
| **VPC Endpoints** | S3 + DynamoDB Gateway | Gateway endpoints free | **$0** |

### **Totale Mensile Stimato**: 
- **Senza VPC**: ~**$47.73/mese**
- **Con VPC**: ~**$114.73/mese**

### Ottimizzazioni Costi

#### 1. **Ridurre Costi Transcribe** (maggior voce di costo)
- Campionare solo un subset di chiamate (es. 10%)
- Ridurre qualità audio (16 kHz invece di 44.1 kHz)
- Usare licenza BASE per clienti che non necessitano riassunti/sentiment

#### 2. **Ridurre Costi Lambda**
- Memory sizing ottimale (256 MB spesso sufficiente)
- Ridurre timeout dove possibile
- Usare Lambda Provisioned Concurrency solo se necessario (per produzione ad alto traffico)

#### 3. **Ridurre Costi S3**
- Lifecycle policy aggressiva (es. 7 giorni invece di 30)
- Transition a S3 Glacier dopo retention period
- Compressione audio (FLAC o Opus invece di WAV)

#### 4. **Ridurre Costi Bedrock**
- Riassunti più brevi (100 parole invece di 200)
- Cache riassunti per conversazioni simili
- Modello più economico (Claude Haiku invece di Sonnet)

#### 5. **Evitare VPC**
- NAT Gateway costa ~$32.40/month per availability zone
- Usare VPC solo per compliance strict o integrazione on-premise
- Default: `EnableVpc=false`

### Free Tier (Primo Anno AWS)

Se account AWS < 12 mesi:
- Lambda: 1M requests + 400.000 GB-seconds free/month
- API Gateway: 1M requests free/month
- S3: 5 GB storage + 20.000 GET + 2.000 PUT free/month
- DynamoDB: 25 GB storage + 25 RCU + 25 WCU free/month
- **Stima First Year**: ~**$40-45/mese** invece di $47.73

### Costi di Produzione (Scala)

Per **10.000 registrazioni/mese**:
- Transcribe: **$720** (costo predominante)
- Bedrock: **$75**
- Lambda: **$15**
- S3: **$3.50**
- Altri: **$10**
- **Totale**: ~**$823.50/mese**

**Raccomandazione**: Per scale superiori, considerare:
- Reserved Capacity per Transcribe (sconto 30%)
- Spot Lambda (non disponibile nativamente, usare alternative)
- CDN CloudFront per distribuzione PDF

---

## 📄 Licenza

MIT License - Vedi [LICENSE](LICENSE) per dettagli completi.

---

## 🤝 Supporto

Per supporto tecnico o domande:
- **Email**: belal.darwish@neuralect.it
- **Documentazione AWS**: 
  - [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/)
  - [Amazon Transcribe](https://docs.aws.amazon.com/transcribe/)
  - [Amazon Bedrock](https://docs.aws.amazon.com/bedrock/)

---

## 📚 Risorse Aggiuntive

### Documentazione Tecnica
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [Amazon Cognito Security](https://docs.aws.amazon.com/cognito/latest/developerguide/security.html)

### Tutorial e Guide
- [Multitenancy in Serverless Architectures](https://aws.amazon.com/blogs/compute/multi-tenant-architectures-on-aws/)
- [GDPR Compliance on AWS](https://aws.amazon.com/compliance/gdpr-center/)
- [Speech-to-Text with Amazon Transcribe](https://aws.amazon.com/transcribe/getting-started/)

---

**Versione README**: 1.0.0  
**Ultimo Aggiornamento**: Gennaio 2025  
**Autore**: Neuralect Team

