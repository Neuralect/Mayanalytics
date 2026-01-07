# Maya Analytics - Assistente Analytics per Setera Centralino

Una piattaforma serverless multitenant enterprise-ready per l'analisi automatica e l'invio schedulato di report analytics basati su dati XML del centralino telefonico Setera, con generazione di insights AI tramite Amazon Bedrock (Claude 3.5 Sonnet).

## 📋 Indice

- [Panoramica](#-panoramica)
- [Parte Tecnica](#️-parte-tecnica)
- [Security](#-security)
- [User Experience](#-user-experience)
- [Deploy](#-deploy)

---

## 🎯 Panoramica

**Maya Analytics** è una piattaforma cloud-native progettata per automatizzare l'analisi e la reportistica dei dati telefonici provenienti dai centralini Setera. Il sistema supporta organizzazioni gerarchiche multi-livello (SuperAdmin, Reseller, Tenant, User) con completo isolamento dei dati e gestione granulare dei permessi.

### Caratteristiche Principali

- ✅ **Report Automatici Schedulati**: Generazione e invio automatico di report personalizzati via email
- ✅ **AI-Powered Insights**: Analisi avanzate generate con Claude 3.5 Sonnet (Amazon Bedrock)
- ✅ **Dashboard Amministrativa**: Interfaccia web moderna con Next.js 16 e React 19
- ✅ **Schedulazione Personalizzata**: Ogni utente può configurare la propria frequenza di ricezione report
- ✅ **Parsing Multi-Report**: Supporto per 5 tipologie di report XML (ACD, IVR, User, Hunt Group, Rule-Based)
- ✅ **Visualizzazione Avanzata**: Grafici generati con matplotlib per analisi visuali
- ✅ **Architettura Multitenant**: Supporto per Reseller con organizzazioni e tenant multipli
- ✅ **GDPR Compliant**: Crittografia, retention policy, isolamento dati

---

## 🏗️ Parte Tecnica

### Architettura

Il sistema utilizza un'architettura serverless moderna basata su AWS:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (AWS Amplify)                       │
│   - Next.js 16 (App Router)                                         │
│   - React 19 + TailwindCSS 4                                        │
│   - Cognito Auth (amazon-cognito-identity-js)                       │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ HTTPS
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│              API GATEWAY (REST API - Cognito Authorizer)            │
│   - /tenants, /users, /resellers                                    │
│   - /profile, /report-history                                       │
│   - /reseller-organizations                                         │
└─────────────────────┬───────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ API Lambda   │ │ Report Gen.  │ │ Email Sender Lambda  │
│ (api.py)     │ │ Lambda       │ │ (email_sender.py)    │
│              │ │ (report_     │ │                      │
│ • CRUD       │ │  generator   │ │ • Amazon SES         │
│ • Cognito    │ │  .py)        │ │ • HTML Templates     │
│ • DynamoDB   │ │              │ │ • UTF-8 Encoding     │
│              │ │ • XML Parse  │ └──────────────────────┘
│              │ │ • Bedrock AI │
│              │ │ • Matplotlib │
└──────────────┘ │ • Charts     │
                 │ • Scheduling │
                 └──────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────────┐
        ▼             ▼             ▼                  ▼
┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ DynamoDB     │ │ Amazon       │ │ Amazon   │ │ Amazon SES   │
│              │ │ Bedrock      │ │ Cognito  │ │              │
│ • Tenants    │ │              │ │          │ │ • noreply@   │
│ • Users      │ │ • Claude 3.5 │ │ • User   │ │   neuralect  │
│ • Resellers  │ │   Sonnet     │ │   Pool   │ │   .it        │
│ • Reports    │ │ • Insights   │ │ • Groups │ │              │
│ • Orgs       │ │   AI         │ │ • JWT    │ └──────────────┘
└──────────────┘ └──────────────┘ └──────────┘
```

### Stack Tecnologico

#### Backend

| Componente | Tecnologia | Versione |
|------------|-----------|----------|
| **Runtime** | Python | 3.13 |
| **IaC** | AWS SAM | 2016-10-31 |
| **Deployment** | CloudFormation | - |
| **HTTP Client** | requests | 2.32.4 |
| **AWS SDK** | boto3 | 1.34.0 |
| **Visualizzazione** | matplotlib | 3.8.4 |
| **Calcoli** | numpy | 1.26.4 |
| **Immagini** | pillow | 10.4.0 |

#### Frontend

| Componente | Tecnologia | Versione |
|------------|-----------|----------|
| **Framework** | Next.js | 16.0.3 |
| **UI Library** | React | 19.2.0 |
| **Styling** | TailwindCSS | 4 |
| **Auth** | amazon-cognito-identity-js | 6.3.16 |
| **Language** | TypeScript | 5 |
| **Build Tool** | Next.js (Turbopack) | - |
| **Hosting** | AWS Amplify Console | - |

#### Servizi AWS

| Servizio | Utilizzo | Note |
|----------|----------|------|
| **Lambda** | Elaborazione serverless | 3 funzioni (API, Report Gen, Email) |
| **API Gateway** | REST API | Cognito Authorizer |
| **DynamoDB** | Database NoSQL | 7 tabelle (Pay-per-request) |
| **Cognito** | Autenticazione | User Pool + 4 gruppi |
| **Bedrock** | AI Generativa | Claude 3.5 Sonnet (eu-central-1) |
| **SES** | Email | Invio report HTML |
| **EventBridge** | Scheduling | Cron ogni minuto per check schedules |
| **Amplify Console** | Frontend Hosting | CI/CD automatico |
| **CloudWatch** | Monitoring | Logs e metriche |

### Lambda Functions

#### 1. **ApiFunction** (`api.py`)
- **Trigger**: API Gateway (ANY /{proxy+})
- **Funzione**: Backend principale per tutte le operazioni CRUD
- **Timeout**: 30s
- **Memory**: 512MB
- **Features**:
  - Gestione utenti (CRUD con Cognito)
  - Gestione tenant
  - Gestione reseller e organizzazioni
  - Report history
  - User profile
  - Invocazione report generator on-demand

#### 2. **ReportGeneratorFunction** (`report_generator.py`)
- **Trigger**: EventBridge Schedule (cron ogni minuto)
- **Funzione**: Genera e invia report schedulati
- **Timeout**: 301s (5 minuti)
- **Memory**: 1536MB (per matplotlib)
- **Workflow**:
  1. **Check Schedule**: Verifica se ci sono utenti da processare in questo minuto
  2. **Fetch XML**: Recupera dati XML da endpoint Setera dell'utente
  3. **Parse XML**: Analizza XML e estrae metriche (5 parser specializzati)
  4. **Generate Charts**: Crea grafici con matplotlib (daily trends, hourly heatmap)
  5. **AI Insights**: Chiama Claude 3.5 Sonnet per analisi approfondite
  6. **Generate HTML**: Crea report HTML con insights + grafici embedded (base64)
  7. **Send Email**: Invoca Email Sender Lambda
  8. **Update History**: Salva record in DynamoDB
  
- **Parser Supportati**:
  - **ACD Report**: Analisi coda chiamate (answer rate, queue time, abandoned calls)
  - **IVR Report**: Metriche IVR (connections, transfers, destinations, failures)
  - **User Report**: Performance agenti (incoming/outgoing, duration, answer rate)
  - **Hunt Group Report**: Distribuzione gruppi (overflow, ring time)
  - **Rule-Based Report**: Routing rules (connection rate, handled calls)

#### 3. **EmailSenderFunction** (`email_sender.py`)
- **Trigger**: Invocazione diretta da ReportGeneratorFunction
- **Funzione**: Invia email HTML via Amazon SES
- **Timeout**: 60s
- **Features**:
  - Encoding UTF-8 robusto per caratteri speciali italiani
  - Gestione emoji nei report
  - Validazione email format
  - Error tracking in DynamoDB
  - HTML + Plain text alternatives

### Database Schema (DynamoDB)

#### 1. **maya-tenants-{env}**
```json
{
  "tenant_id": "uuid",
  "name": "string",
  "status": "active|inactive",
  "created_at": "iso-timestamp"
}
```
- **Key**: `tenant_id` (HASH)

#### 2. **maya-users-{env}**
```json
{
  "user_id": "cognito-sub",
  "tenant_id": "uuid",
  "email": "string",
  "name": "string",
  "role": "SuperAdmin|Reseller|Admin|User",
  "xml_endpoint": "https://...",
  "xml_token": "string",
  "report_enabled": true|false,
  "report_schedule": "0 9 * * 1-5",
  "report_email": "custom@email.com",
  "created_at": "iso-timestamp"
}
```
- **Key**: `user_id` (HASH) + `tenant_id` (RANGE)
- **GSI**: `email-index`, `tenant-index`

#### 3. **maya-report-history-{env}**
```json
{
  "user_id": "cognito-sub",
  "report_timestamp": "iso-timestamp",
  "status": "sent|failed|processing",
  "sent_at": "iso-timestamp",
  "error_message": "string (optional)",
  "ttl": 1234567890
}
```
- **Key**: `user_id` (HASH) + `report_timestamp` (RANGE)
- **TTL**: Enabled (automatic cleanup)

#### 4. **maya-reseller-tenants-{env}**
```json
{
  "reseller_id": "cognito-sub",
  "tenant_id": "uuid",
  "assigned_at": "iso-timestamp"
}
```
- **Key**: `reseller_id` (HASH) + `tenant_id` (RANGE)
- **GSI**: `tenant-index`

#### 5-7. **Reseller Organizations Tables**
- `maya-reseller-organizations-{env}`: Organizzazioni reseller
- `maya-reseller-user-organizations-{env}`: Mapping utenti-organizzazioni
- `maya-reseller-org-tenants-{env}`: Mapping organizzazioni-tenant

### Flusso Completo: Generazione Report

```
┌─────────────────────────────────────────────────────────────┐
│ 1. EventBridge Schedule (cron: * * * * ? *)                │
│    Trigger ogni minuto                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ReportGeneratorFunction - Check Schedules               │
│    - Scan users_table                                       │
│    - Filter: report_enabled=true                            │
│    - Parse cron: "0 9 * * 1-5" (daily 9am, Mon-Fri)       │
│    - Match current time with user schedules                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼ (for each matched user)
┌─────────────────────────────────────────────────────────────┐
│ 3. Fetch XML Data                                           │
│    GET xml_endpoint                                         │
│    Headers: {"Authorization": f"Bearer {xml_token}"}       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Parse XML Report                                         │
│    - Detect report type (ACD/IVR/User/HuntGroup/RuleBased) │
│    - Extract metrics, timestamps, entity names              │
│    - Build structured data dict                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Generate Charts (matplotlib)                             │
│    - Daily trend line chart (last 7-30 days)               │
│    - Hourly heatmap (color-coded by volume)                │
│    - Convert to base64 PNG                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Generate AI Insights (Claude 3.5 Sonnet)                │
│    POST bedrock-runtime.InvokeModel                         │
│    Model: anthropic.claude-3-5-sonnet-20240620-v1:0        │
│    Prompt: Specialized per tipo report (italiano)          │
│    Response: Insights strutturati (~1500 tokens)           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Build HTML Email                                         │
│    - Header con logo e data                                 │
│    - AI Insights (formatted HTML)                           │
│    - Charts embedded (base64)                               │
│    - Metrics tables                                         │
│    - Footer con link dashboard                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Invoke EmailSenderFunction                               │
│    lambda_client.invoke(                                    │
│      FunctionName='maya-email-sender-v2-{env}',            │
│      Payload={                                              │
│        'to_email': user_report_email,                       │
│        'subject': '🤖 Maya Analytics - Report...',         │
│        'html_content': html,                                │
│        'user_id': user_id                                   │
│      }                                                       │
│    )                                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. Send Email (Amazon SES)                                  │
│    ses.send_email(                                          │
│      Source='noreply@neuralect.it',                        │
│      Destination={'ToAddresses': [user_email]},            │
│      Message={'Subject': {...}, 'Body': {'Html': {...}}}   │
│    )                                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. Update Report History (DynamoDB)                        │
│     reports_table.put_item({                                │
│       'user_id': user_id,                                   │
│       'report_timestamp': now,                              │
│       'status': 'sent',                                     │
│       'sent_at': now,                                       │
│       'ttl': now + 90 days                                  │
│     })                                                      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
                    ✅ COMPLETATO
```

---

## 🔒 Security

### Autenticazione e Autorizzazione

#### 1. **Amazon Cognito User Pool**

**Configurazione User Pool**:
- **Name**: `maya-analytics-{env}`
- **Username Attributes**: Email (auto-verified)
- **Custom Attributes**:
  - `custom:tenant_id`: Associazione tenant (String, mutable)
  
**Password Policy**:
```yaml
MinimumLength: 8
RequireUppercase: true
RequireLowercase: true
RequireNumbers: true
RequireSymbols: true
```

**Token Validity**:
- Access Token: 60 minuti
- ID Token: 60 minuti  
- Refresh Token: 30 giorni

**Authentication Flows**:
- `ALLOW_USER_PASSWORD_AUTH`: Login standard email/password
- `ALLOW_REFRESH_TOKEN_AUTH`: Refresh automatico sessione
- `ALLOW_USER_SRP_AUTH`: Secure Remote Password (recommended)
- `ALLOW_ADMIN_USER_PASSWORD_AUTH`: Admin password management

#### 2. **Modello di Autorizzazione Gerarchico a 4 Livelli**

```
┌─────────────────────────────────────────────────┐
│            SUPERADMIN                           │
│  ✓ Gestisce TUTTO il sistema                   │
│  ✓ Crea/modifica tenant, reseller, admin        │
│  ✓ Context switching (visualizza come tenant)  │
│  ✓ Accesso dashboard completa                   │
│  ✓ Gestione organizzazioni reseller             │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌───────────────────┐   ┌───────────────────┐
│     RESELLER      │   │      ADMIN        │
│  ✓ Crea tenant    │   │  ✓ Gestisce       │
│    propri         │   │    utenti tenant  │
│  ✓ Organizzazioni │   │  ✓ Visualizza     │
│    multi-tenant   │   │    report tenant  │
│  ✓ Crea admin per │   │  ✓ Gestisce       │
│    i tenant       │   │    connettori XML │
│  ✓ Context        │   └─────────┬─────────┘
│    switching      │             │
└─────────┬─────────┘             │
          │                       │
          └───────────┬───────────┘
                      ▼
          ┌───────────────────────┐
          │       USER            │
          │  ✓ Riceve report      │
          │    automatici via     │
          │    email              │
          │  ✗ NO accesso         │
          │    dashboard          │
          └───────────────────────┘
```

**Permessi Dettagliati**:

| Azione | SuperAdmin | Reseller | Admin | User |
|--------|-----------|----------|-------|------|
| Crea tenant | ✅ | ✅ (propri) | ❌ | ❌ |
| Crea reseller | ✅ | ❌ | ❌ | ❌ |
| Crea admin | ✅ | ✅ (per propri tenant) | ❌ | ❌ |
| Crea user | ✅ | ✅ (per propri tenant) | ✅ (proprio tenant) | ❌ |
| Visualizza tutti i tenant | ✅ | ✅ (propri) | ❌ | ❌ |
| Context switching | ✅ | ✅ (propri tenant) | ❌ | ❌ |
| Accesso dashboard | ✅ | ✅ | ✅ | ❌ |
| Gestione organizzazioni | ✅ | ✅ (proprie) | ❌ | ❌ |
| Modifica XML connector | ✅ | ✅ (propri utenti) | ✅ (proprio tenant) | ❌ |
| Riceve report email | ✅ | ✅ | ✅ | ✅ |

#### 3. **API Gateway Authorization**

**Cognito Authorizer**:
```yaml
Auth:
  DefaultAuthorizer: CognitoAuth
  Authorizers:
    CognitoAuth:
      UserPoolArn: !GetAtt CognitoUserPool.Arn
```

**Request Headers**:
```http
Authorization: Bearer {idToken}
```

**Token Validation**:
- Verifica firma JWT con JWKS pubblico di Cognito
- Verifica issuer: `https://cognito-idp.eu-central-1.amazonaws.com/{userPoolId}`
- Verifica audience: Client ID
- Verifica scadenza (exp claim)

#### 4. **Row-Level Security (Isolamento Dati)**

Ogni endpoint Lambda implementa filtering automatico basato su ruolo e tenant:

```python
def get_user_from_event(event):
    """Extract user info from Cognito authorizer"""
    claims = event['requestContext']['authorizer']['claims']
    
    return {
        'user_id': claims['sub'],
        'email': claims['email'],
        'tenant_id': claims.get('custom:tenant_id'),
        'groups': claims.get('cognito:groups', [])
    }

def check_permissions(user, action, resource):
    """Check if user can perform action on resource"""
    
    if 'SuperAdmin' in user['groups']:
        # SuperAdmin ha accesso a tutto
        return True
    
    if 'Reseller' in user['groups']:
        # Reseller vede solo i suoi tenant
        if action == 'read:tenant':
            return resource['tenant_id'] in get_reseller_tenants(user['user_id'])
    
    if 'Admin' in user['groups']:
        # Admin vede solo il proprio tenant
        if action == 'read:user':
            return resource['tenant_id'] == user['tenant_id']
    
    if 'User' in user['groups']:
        # User può solo modificare se stesso
        if action == 'update:profile':
            return resource['user_id'] == user['user_id']
    
    return False
```

### Crittografia

#### 1. **Data at Rest**

| Risorsa | Metodo | Key Management |
|---------|--------|---------------|
| **DynamoDB** | SSE (Server-Side Encryption) | AWS Managed (default) |
| **CloudWatch Logs** | SSE-KMS | AWS Managed |
| **Lambda Environment Variables** | KMS | AWS Managed |

**DynamoDB Encryption**:
- Tutte le tabelle hanno encryption-at-rest abilitata di default
- Utilizzo di AWS Managed Keys (no costi aggiuntivi)
- Transparent per l'applicazione

#### 2. **Data in Transit**

| Connessione | Protocollo | Versione Minima |
|------------|-----------|----------------|
| **Frontend → API Gateway** | HTTPS/TLS | 1.2 |
| **API Gateway → Lambda** | HTTPS (interno AWS) | 1.2 |
| **Lambda → DynamoDB** | HTTPS | 1.2 |
| **Lambda → Bedrock** | HTTPS | 1.2 |
| **Lambda → Cognito** | HTTPS | 1.2 |
| **Lambda → SES** | HTTPS | 1.2 |
| **Lambda → Setera (XML endpoint)** | HTTPS | 1.2 |

**Certificate Management**:
- API Gateway: Certificate gestito da AWS (wildcard *.execute-api.eu-central-1.amazonaws.com)
- Amplify: Certificate gestito automaticamente (ACM)

#### 3. **Secrets Management**

**Strategia**:
- ❌ NO secrets hardcoded nel codice
- ❌ NO secrets in environment variables (pubbliche)
- ✅ `xml_token`: Salvato in DynamoDB (encrypted at rest)
- ✅ Cognito User Pool ID/Client ID: Environment variables (pubblici)
- ✅ AWS credentials: IAM Roles (automatic temporary credentials)

```python
# ❌ BAD - Never do this
API_KEY = "sk-1234567890abcdef"

# ✅ GOOD - Load from DynamoDB
user = users_table.get_item(Key={'user_id': user_id})
xml_token = user['xml_token']  # Encrypted at rest in DynamoDB
```

### GDPR Compliance

#### 1. **Right to Erasure (Cancellazione Dati)**

**TTL DynamoDB**:
```yaml
ReportHistoryTable:
  TimeToLiveSpecification:
    AttributeName: ttl
    Enabled: true
```
- Report history eliminata automaticamente dopo 90 giorni
- TTL calcolato: `current_timestamp + 90 days`

**User Deletion**:
```python
def delete_user(user_id):
    # 1. Delete from Cognito
    cognito.admin_delete_user(UserPoolId=USER_POOL_ID, Username=user_id)
    
    # 2. Delete from DynamoDB
    users_table.delete_item(Key={'user_id': user_id, 'tenant_id': tenant_id})
    
    # 3. Delete report history
    reports = reports_table.query(KeyConditionExpression=Key('user_id').eq(user_id))
    for report in reports['Items']:
        reports_table.delete_item(Key={'user_id': user_id, 'report_timestamp': report['report_timestamp']})
```

#### 2. **Data Minimization**

**Dati Raccolti** (minimo necessario):
- Email (per autenticazione e invio report)
- Nome (per personalizzazione)
- XML endpoint + token (per recupero dati centralino)
- Report schedule (per schedulazione)
- Custom report email (opzionale)

**Dati NON Raccolti**:
- ❌ Numero di telefono
- ❌ Indirizzo fisico
- ❌ Data di nascita
- ❌ Dati sensibili non necessari

#### 3. **Right to Access**

**API `/api/profile`**:
```http
GET /api/profile
Authorization: Bearer {token}

Response:
{
  "user": {
    "user_id": "...",
    "email": "user@example.com",
    "name": "...",
    "tenant_id": "...",
    "report_enabled": true,
    "report_schedule": "0 9 * * 1-5",
    "xml_endpoint": "https://...",
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

**API `/api/users/{user_id}/report-history`**:
- Utente può visualizzare lo storico dei propri report inviati
- Include timestamp, status (sent/failed), error_message

#### 4. **Data Residency (Residenza Dati)**

**Region**: `eu-central-1` (Francoforte, Germania)

Tutti i servizi deployati in EU:
- ✅ Lambda: eu-central-1
- ✅ DynamoDB: eu-central-1
- ✅ Cognito: eu-central-1
- ✅ Bedrock: eu-central-1
- ✅ SES: eu-central-1
- ✅ CloudWatch: eu-central-1
- ✅ API Gateway: eu-central-1
- ✅ Amplify: eu-central-1

**Cross-Region**: ❌ Nessun dato lascia la EU

#### 5. **Consent Management**

**Report Scheduling**:
```python
user['report_enabled'] = True  # Opt-in esplicito
user['report_schedule'] = "0 9 * * 1-5"  # Personalizzabile
user['report_email'] = "user@example.com"  # Destinazione custom
```

**Disable Reports**:
```http
PUT /api/users/{user_id}
{
  "report_enabled": false  // User può disabilitare in qualsiasi momento
}
```

### Logging e Audit

#### 1. **CloudWatch Logs**

**Retention**: 30 giorni (configurabile)

**Log Groups**:
- `/aws/lambda/maya-api-{env}`
- `/aws/lambda/maya-report-generator-{env}`
- `/aws/lambda/maya-email-sender-v2-{env}`

**Log Level**: `INFO` (production), `DEBUG` (dev)

**Dati Sensibili Esclusi**:
- ❌ Password (mai loggati)
- ❌ Cognito tokens (solo "Token present: true/false")
- ❌ XML content (troppo grande e potenzialmente sensibile)
- ✅ User IDs, email (per troubleshooting)
- ✅ Timestamps, status, error messages

#### 2. **Audit Trail**

**Tracking Modifiche**:
```python
# Ogni record DynamoDB include:
{
  "created_at": "2024-01-15T10:30:00Z",  # Timestamp creazione
  "updated_at": "2024-01-20T14:25:00Z",  # Ultimo update
  "created_by": "admin@example.com",     # Chi ha creato
  "updated_by": "superadmin@example.com" # Chi ha modificato
}
```

### IAM e Least Privilege

#### 1. **Lambda Execution Roles**

**ApiFunction Role**:
```yaml
Policies:
  - DynamoDBCrudPolicy:
      TableName: maya-tenants-{env}
  - DynamoDBCrudPolicy:
      TableName: maya-users-{env}
  - DynamoDBCrudPolicy:
      TableName: maya-report-history-{env}
  - DynamoDBCrudPolicy:
      TableName: maya-reseller-*
  - Statement:
    - Effect: Allow
      Action:
        - cognito-idp:AdminCreateUser
        - cognito-idp:AdminDeleteUser
        - cognito-idp:AdminUpdateUserAttributes
        - cognito-idp:AdminGetUser
        - cognito-idp:ListUsers
        - cognito-idp:AdminAddUserToGroup
        - cognito-idp:AdminRemoveUserFromGroup
        - cognito-idp:AdminSetUserPassword
      Resource: !GetAtt CognitoUserPool.Arn
  - Statement:
    - Effect: Allow
      Action: lambda:InvokeFunction
      Resource: !GetAtt ReportGeneratorFunction.Arn
```

**ReportGeneratorFunction Role**:
```yaml
Policies:
  - DynamoDBCrudPolicy:
      TableName: maya-users-{env}
  - DynamoDBCrudPolicy:
      TableName: maya-report-history-{env}
  - Statement:
    - Effect: Allow
      Action: bedrock:InvokeModel
      Resource: arn:aws:bedrock:eu-central-1::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0
  - Statement:
    - Effect: Allow
      Action: lambda:InvokeFunction
      Resource: !Sub "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:maya-email-sender-v2-${Environment}"
```

**EmailSenderFunction Role**:
```yaml
Policies:
  - DynamoDBCrudPolicy:
      TableName: maya-report-history-{env}
  - Statement:
    - Effect: Allow
      Action:
        - ses:SendEmail
        - ses:SendRawEmail
      Resource: "*"  # SES requires wildcard for verified identities
```

#### 2. **API Gateway Resource Policy**

**CORS Policy**:
```yaml
Cors:
  AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"
  AllowHeaders: "'Content-Type,Authorization,X-Requested-With'"
  AllowOrigin: "'*'"  # Production: specify exact domain
  AllowCredentials: false
```

**Rate Limiting**:
- Default throttle: 10,000 requests/second
- Burst: 5,000 requests
- Per-user throttle: Configurabile con Usage Plans

### Best Practices Implementate

#### 1. **Code Security**

✅ **Input Validation**:
```python
def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_report_schedule(schedule: str) -> bool:
    # Validate cron expression format
    parts = schedule.split()
    if len(parts) != 5:
        return False
    # Additional cron validation...
    return True
```

✅ **Error Handling**:
```python
try:
    result = process_user_data(user_input)
except ValidationError as e:
    logger.error(f"Validation failed: {str(e)}")
    return {'statusCode': 400, 'body': json.dumps({'error': 'Invalid input'})}
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}")
    return {'statusCode': 500, 'body': json.dumps({'error': 'Internal server error'})}
```

✅ **SQL Injection Prevention**:
- Utilizzo DynamoDB (NoSQL) con AWS SDK
- Parametrizzazione automatica query
- No raw SQL/NoSQL queries

#### 2. **Network Security**

✅ **Public Access Block** (future S3 bucket):
```yaml
PublicAccessBlockConfiguration:
  BlockPublicAcls: true
  BlockPublicPolicy: true
  IgnorePublicAcls: true
  RestrictPublicBuckets: true
```

✅ **VPC (Optional)**:
- Lambda funzioni possono essere deployate in VPC private
- NAT Gateway per accesso internet outbound
- Security Groups per controllo traffico

#### 3. **Compliance Certifications AWS**

AWS Services utilizzati sono conformi a:
- ✅ **ISO 27001** (Security Management)
- ✅ **ISO 27017** (Cloud Security)
- ✅ **ISO 27018** (Cloud Privacy)
- ✅ **SOC 2 Type II** (Security, Availability, Confidentiality)
- ✅ **GDPR** (EU Data Protection)
- ✅ **PCI DSS** (Payment Card Industry - if needed)

---

## 👤 User Experience

### Dashboard Web

#### 1. **Autenticazione**

**Login Flow**:
```
1. User visita https://app.mayaanalytics.com
2. Vede LoginForm
3. Inserisce email + password
4. Cognito autentica
5. Se primo accesso → ChangePasswordForm (password temporanea)
6. Altrimenti → Redirect dashboard
```

**Forgot Password**:
- Click "Password dimenticata?"
- Inserisci email
- Cognito invia codice verifica via email
- Inserisci codice + nuova password
- Password resettata

**Session Management**:
- Access token valido 60 minuti
- Refresh automatico in background
- Logout manuale disponibile in header

#### 2. **Role-Based UI**

**SuperAdmin Dashboard**:
```
┌────────────────────────────────────────────────┐
│  Maya Analytics         👤 admin@example.com  │
│                         [Context: Global ▼]    │
├────────────────────────────────────────────────┤
│  📊 Dashboard                                  │
│  👥 Gestione Utenti      [+ Crea Utente]      │
│  🏢 Gestione Tenant      [+ Crea Tenant]      │
│  🤝 Gestione Reseller    [+ Crea Reseller]    │
│  👔 Gestione SuperAdmin  [+ Crea SuperAdmin]  │
│  🏛️  Organizzazioni      [+ Crea Org]         │
│  📧 Report History                             │
└────────────────────────────────────────────────┘
```

**Reseller Dashboard**:
```
┌────────────────────────────────────────────────┐
│  Maya Analytics         👤 reseller@co.com    │
│                         [Context: Acme Inc ▼]  │
├────────────────────────────────────────────────┤
│  📊 Dashboard                                  │
│  🏢 I Miei Tenant        [+ Crea Tenant]      │
│  🏛️  Le Mie Org          [+ Crea Org]         │
│  👥 Utenti Tenant        [+ Crea Admin/User]  │
│  📧 Report History                             │
└────────────────────────────────────────────────┘
```

**Admin Dashboard**:
```
┌────────────────────────────────────────────────┐
│  Maya Analytics         👤 admin@company.com  │
├────────────────────────────────────────────────┤
│  📊 Dashboard                                  │
│  👥 Gestione Utenti      [+ Crea Utente]      │
│  📧 Report History                             │
│  ⚙️  Connettori XML                            │
└────────────────────────────────────────────────┘
```

**User Dashboard**:
```
┌────────────────────────────────────────────────┐
│  Maya Analytics         👤 user@company.com   │
├────────────────────────────────────────────────┤
│                                                │
│  ⚠️  Accesso non disponibile                  │
│                                                │
│  Gli utenti finali ricevono solo report       │
│  automatici via email.                         │
│  Non è necessario accedere al sistema.         │
│                                                │
└────────────────────────────────────────────────┘
```

#### 3. **Gestione Utenti**

**Tabella Utenti**:
```
┌───────────────────────────────────────────────────────────┐
│  Gestione Utenti                    [+ Crea Utente]      │
├───────────────────────────────────────────────────────────┤
│  🔍 Cerca: [___________]  Tenant: [Tutti ▼]  Ruolo: [Tutti ▼] │
├───────────────────────────────────────────────────────────┤
│  Nome          Email              Tenant    Report  [Azioni] │
│  ────────────────────────────────────────────────────────── │
│  Mario Rossi   mario@acme.com    Acme Inc  ✅      [✏️][🗑️] │
│  Laura Bianchi laura@acme.com    Acme Inc  ❌      [✏️][🗑️] │
│  ...                                                         │
└───────────────────────────────────────────────────────────┘
```

**Modal Creazione Utente**:
```
┌──────────────────────────────────────┐
│  Crea Nuovo Utente            [✕]   │
├──────────────────────────────────────┤
│  Nome: [____________________]        │
│  Email: [____________________]       │
│  Tenant: [Seleziona tenant ▼]       │
│  Password: [____________________]    │
│                                      │
│  📊 Configurazione Report            │
│  ☑️ Abilita Report Automatici       │
│  Email Report: [same as user email ▼]│
│  Schedule: [0 9 * * 1-5 ▼]          │
│            (Lun-Ven ore 9:00)       │
│                                      │
│  🔗 Connettore XML                   │
│  Endpoint: [____________________]    │
│  Token: [____________________]       │
│                                      │
│  [Annulla]  [Crea Utente]           │
└──────────────────────────────────────┘
```

**Schedule Picker**:
```
Frequenza: [Giornaliero ▼]
           - Giornaliero
           - Settimanale
           - Mensile

Orario: [09:00 ▼]
Giorni: ☑️ Lun ☑️ Mar ☑️ Mer ☑️ Gio ☑️ Ven ☐ Sab ☐ Dom

Preview: "Ogni giorno lavorativo alle 9:00"
Cron: 0 9 * * 1-5
```

#### 4. **Context Selector (SuperAdmin/Reseller)**

**Flow**:
```
1. SuperAdmin/Reseller effettua login
2. Vede Context Selector dopo autenticazione:

┌────────────────────────────────────────────┐
│  Seleziona Contesto                        │
├────────────────────────────────────────────┤
│  🌐 Visualizzazione Globale                │
│     Gestisci tutti i tenant e reseller     │
│     [Seleziona]                            │
├────────────────────────────────────────────┤
│  🏢 Tenant Specifici                       │
│                                            │
│  ○ Acme Inc                                │
│  ○ Beta Corp                               │
│  ○ Gamma Ltd                               │
│     [Seleziona]                            │
└────────────────────────────────────────────┘

3. Scelta salvata in sessionStorage
4. Header dashboard mostra context corrente
5. Può cambiare context da dropdown in header
```

#### 5. **Report Email UX**

**Email Template**:
```html
┌─────────────────────────────────────────────────────────┐
│  From: Maya Analytics <noreply@neuralect.it>           │
│  To: user@company.com                                   │
│  Subject: 🤖 Maya Analytics - Report ACD Acme Inc      │
│          (15 Gennaio 2024)                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🤖 MAYA ANALYTICS - REPORT GIORNALIERO                │
│                                                         │
│  Ciao Mario,                                            │
│                                                         │
│  Ecco il tuo report analytics per Acme Inc - ACD Queue │
│  generato il 15 Gennaio 2024 alle 09:00.              │
│                                                         │
│  ═══════════════════════════════════════════════════    │
│  📊 ANALISI AI (powered by Claude 3.5 Sonnet)          │
│  ═══════════════════════════════════════════════════    │
│                                                         │
│  🎯 INSIGHTS PRINCIPALI                                │
│  • Tasso di risposta eccellente (92.5%)                │
│  • Picco chiamate tra 10:00-12:00                      │
│  • Tempo medio attesa ottimale (18 secondi)            │
│                                                         │
│  📈 TREND SETTIMANALE                                   │
│  • +15% chiamate rispetto a lunedì scorso              │
│  • Miglioramento tempo risposta del 8%                 │
│                                                         │
│  ⚠️ AREE DI ATTENZIONE                                 │
│  • Chiamate abbandonate in aumento dopo 30s attesa     │
│  • Considerare aumento personale ore 11:00-12:00       │
│                                                         │
│  💡 RACCOMANDAZIONI                                     │
│  • Monitorare picco mattutino                          │
│  • Ottimizzare routing coda prioritaria                │
│                                                         │
│  ═══════════════════════════════════════════════════    │
│  📈 GRAFICI ANALYTICS                                   │
│  ═══════════════════════════════════════════════════    │
│                                                         │
│  [Grafico trend chiamate ultimi 7 giorni - line chart] │
│  [Heatmap oraria distribuzione chiamate - color grid]  │
│                                                         │
│  ═══════════════════════════════════════════════════    │
│  📊 METRICHE DETTAGLIATE                               │
│  ═══════════════════════════════════════════════════    │
│                                                         │
│  Totale Chiamate: 1,234                                │
│  Risposte: 1,142 (92.5%)                               │
│  Perse: 92 (7.5%)                                      │
│  Tempo Medio Attesa: 18s                               │
│  Durata Media: 4m 32s                                  │
│                                                         │
│  ═══════════════════════════════════════════════════    │
│                                                         │
│  🔗 Accedi alla dashboard per maggiori dettagli        │
│     https://app.mayaanalytics.com                      │
│                                                         │
│  ────────────────────────────────────────────────       │
│  Powered by Maya Analytics | Neuralect                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 6. **Responsive Design**

**Mobile-First Approach**:
- ✅ TailwindCSS responsive utilities
- ✅ Hamburger menu per mobile
- ✅ Touch-friendly buttons (min 44x44px)
- ✅ Tables scrollano orizzontalmente
- ✅ Modals full-screen su mobile

**Breakpoints**:
```css
sm: 640px   /* Tablets portrait */
md: 768px   /* Tablets landscape */
lg: 1024px  /* Desktop */
xl: 1280px  /* Large desktop */
2xl: 1536px /* Extra large */
```

#### 7. **Accessibility**

✅ **WCAG 2.1 Level AA**:
- Contrast ratio ≥ 4.5:1 per testo
- Focus indicators visibili
- Keyboard navigation completa
- ARIA labels per screen readers
- Form validation con messaggi chiari

✅ **Semantic HTML**:
```tsx
<nav aria-label="Main navigation">
<main role="main">
<button aria-label="Create new user">
<table role="table" aria-label="Users list">
```

#### 8. **Loading States & Feedback**

**Loading Spinners**:
```tsx
{loading ? (
  <div className="flex justify-center items-center">
    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500" />
    <p>Caricamento...</p>
  </div>
) : (
  <UserTable users={users} />
)}
```

**Toast Notifications**:
```
┌──────────────────────────────────┐
│  ✅ Utente creato con successo! │  (Auto-dismiss 3s)
└──────────────────────────────────┘

┌──────────────────────────────────┐
│  ❌ Errore: Email già esistente  │  (Manual dismiss)
└──────────────────────────────────┘
```

**Confirmation Dialogs**:
```
┌─────────────────────────────────────┐
│  Conferma Eliminazione        [✕]  │
├─────────────────────────────────────┤
│  Sei sicuro di voler eliminare      │
│  l'utente "Mario Rossi"?            │
│                                     │
│  ⚠️ Questa azione è irreversibile  │
│                                     │
│  [Annulla]  [🗑️ Elimina]          │
└─────────────────────────────────────┘
```

#### 9. **Error Handling UX**

**Empty States**:
```
┌─────────────────────────────────────┐
│  👥 Gestione Utenti                │
├─────────────────────────────────────┤
│                                     │
│          📭                         │
│     Nessun utente trovato          │
│                                     │
│  Inizia creando il primo utente    │
│  [+ Crea Utente]                   │
│                                     │
└─────────────────────────────────────┘
```

**Error Pages**:
```
┌─────────────────────────────────────┐
│          ⚠️                         │
│     Errore di Connessione          │
│                                     │
│  Non riusciamo a connetterci       │
│  al server. Riprova più tardi.     │
│                                     │
│  [🔄 Riprova]                      │
└─────────────────────────────────────┘
```

#### 10. **Performance UX**

**Optimization Strategies**:
- ✅ Next.js 16 Server Components (RSC)
- ✅ Incremental Static Regeneration (ISR)
- ✅ Image optimization (next/image)
- ✅ Code splitting automatico
- ✅ Prefetching automatico link
- ✅ React 19 Suspense boundaries

**Loading Performance**:
- First Contentful Paint (FCP): < 1.8s
- Largest Contentful Paint (LCP): < 2.5s
- Time to Interactive (TTI): < 3.5s

---

## 🚀 Deploy

### Prerequisiti

#### 1. **AWS Account Setup**

**Requisiti**:
- AWS Account attivo
- AWS CLI v2 installato
- SAM CLI installato
- Permessi IAM necessari:
  - CloudFormation (CreateStack, UpdateStack, DeleteStack)
  - Lambda (CreateFunction, UpdateFunctionCode, etc.)
  - API Gateway (CreateRestApi, etc.)
  - DynamoDB (CreateTable, etc.)
  - Cognito (CreateUserPool, etc.)
  - IAM (CreateRole, AttachRolePolicy)
  - S3 (CreateBucket - per SAM deployment)

**Installazione AWS CLI**:
```bash
# Windows (PowerShell as Admin)
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

# Mac
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

**Configurazione Credenziali**:
```bash
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ...
# Default region name: eu-central-1
# Default output format: json

# Verifica configurazione
aws sts get-caller-identity
```

**Installazione SAM CLI**:
```bash
# Windows (PowerShell as Admin)
choco install aws-sam-cli

# Mac
brew install aws-sam-cli

# Linux
pip install aws-sam-cli

# Verifica installazione
sam --version
# SAM CLI, version 1.x.x
```

#### 2. **Amazon SES Setup** (Critical!)

**Email Verification**:
```bash
# 1. Verifica sender email
aws ses verify-email-identity --email-address noreply@neuralect.it --region eu-central-1

# 2. Check inbox per email conferma
# Click link verifica

# 3. Verifica status
aws ses get-identity-verification-attributes \
    --identities noreply@neuralect.it \
    --region eu-central-1

# Output:
# {
#   "VerificationAttributes": {
#     "noreply@neuralect.it": {
#       "VerificationStatus": "Success"
#     }
#   }
# }
```

**Domain Verification** (Recommended for production):
```bash
# 1. Verifica dominio completo
aws ses verify-domain-identity --domain neuralect.it --region eu-central-1

# 2. Aggiungi record TXT DNS:
# Name: _amazonses.neuralect.it
# Type: TXT
# Value: [token from AWS response]

# 3. Configura DKIM (Domain Keys Identified Mail)
aws ses set-identity-dkim-enabled \
    --identity neuralect.it \
    --dkim-enabled \
    --region eu-central-1

# 4. Aggiungi 3 record CNAME DNS per DKIM
```

**Sandbox vs Production**:
```bash
# Check sandbox status
aws sesv2 get-account --region eu-central-1

# Se in sandbox (default):
# - Puoi inviare solo a email verificate
# - Limite: 200 email/giorno, 1 email/secondo

# Request production access:
aws support create-case \
    --subject "Request to move out of SES Sandbox" \
    --communication-body "We need to send automated analytics reports to our customers..." \
    --category-code "service-limit-increase" \
    --service-code "ses"
```

**IMPORTANT**: Durante sviluppo, verifica manualmente le email dei destinatari test!

### Deploy Backend (AWS SAM)

#### 1. **Build Lambda Layers**

```bash
cd Deploy

# Build tutte le funzioni Lambda
sam build

# Output:
# Building codeuri: src/api runtime: python3.13 ...
# Building codeuri: src/report-generator runtime: python3.13 ...
# Building codeuri: src/email-sender runtime: python3.13 ...
# Build Succeeded
```

**Troubleshooting Build**:
```bash
# Se errore "requirements.txt not found":
cd src/report-generator
pip install -r requirements.txt --target .

# Se errore matplotlib:
# matplotlib richiede compilazione C, usa Lambda Layer o Docker build
sam build --use-container
```

#### 2. **Deploy Stack**

**Prima Deploy**:
```bash
sam deploy --guided

# Prompt interattivo:
# Stack Name [maya-analytics]: maya-analytics-prod
# AWS Region [eu-central-1]: eu-central-1
# Parameter Environment [prod]: prod
# Parameter ProjectName []: MayaAnalytics
# Confirm changes before deploy [Y/n]: Y
# Allow SAM CLI IAM role creation [Y/n]: Y
# Allow Lambda function url authorization [Y/n]: N
# Disable rollback [y/N]: N
# Save arguments to configuration file [Y/n]: Y
# SAM configuration file [samconfig.toml]: samconfig.toml
# SAM configuration environment [default]: default

# Deploy inizia...
# Creazione stack CloudFormation...
# ⏳ Creazione risorse (10-15 minuti prima volta)
```

**Deploy Successivi** (più veloci):
```bash
# Usa configurazione salvata
sam deploy

# Oppure specifica environment
sam deploy --parameter-overrides Environment=dev

# Oppure deploy rapido senza changeset
sam deploy --no-confirm-changeset
```

**Deploy Output**:
```yaml
CloudFormation outputs from deployed stack
-----------------------------------------------
Outputs:
-----------------------------------------------
Key: ApiUrl
Description: API Gateway URL
Value: https://78jt5iyn1f.execute-api.eu-central-1.amazonaws.com/Prod

Key: UserPoolId
Description: Cognito User Pool ID
Value: eu-central-1_eIs0HT7aN

Key: UserPoolClientId
Description: Cognito User Pool Client ID
Value: 41erklu7iorpilb2dn98avf76f

Key: Region
Description: AWS Region
Value: eu-central-1
-----------------------------------------------
```

**Salva questi valori**: Servono per configurare il frontend!

#### 3. **Post-Deploy Configuration**

**Crea SuperAdmin Iniziale**:
```bash
# 1. Crea utente Cognito
aws cognito-idp admin-create-user \
    --user-pool-id eu-central-1_eIs0HT7aN \
    --username admin@neuralect.it \
    --user-attributes Name=email,Value=admin@neuralect.it Name=email_verified,Value=true \
    --temporary-password TempPass123! \
    --message-action SUPPRESS \
    --region eu-central-1

# 2. Aggiungi a gruppo SuperAdmin
aws cognito-idp admin-add-user-to-group \
    --user-pool-id eu-central-1_eIs0HT7aN \
    --username admin@neuralect.it \
    --group-name SuperAdmin \
    --region eu-central-1

# 3. Crea record DynamoDB
aws dynamodb put-item \
    --table-name maya-users-prod \
    --item '{
        "user_id": {"S": "[cognito-sub-from-previous-command]"},
        "tenant_id": {"S": "system"},
        "email": {"S": "admin@neuralect.it"},
        "name": {"S": "Super Admin"},
        "role": {"S": "SuperAdmin"},
        "created_at": {"S": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}
    }' \
    --region eu-central-1

# 4. Login e cambio password
# Vai a frontend, login con admin@neuralect.it / TempPass123!
# Sistema chiederà cambio password obbligatorio
```

**Verifica Deploy**:
```bash
# Test API Gateway
curl https://78jt5iyn1f.execute-api.eu-central-1.amazonaws.com/Prod/

# Test Lambda
aws lambda invoke \
    --function-name maya-api-prod \
    --payload '{"httpMethod":"GET","path":"/"}' \
    --region eu-central-1 \
    response.json

cat response.json

# Check CloudWatch Logs
aws logs tail /aws/lambda/maya-api-prod --follow
```

### Deploy Frontend (AWS Amplify)

#### 1. **Configura Repository Git**

**Push Codice a GitHub**:
```bash
cd Deploy/frontend

# Inizializza git (se non già fatto)
git init
git add .
git commit -m "Initial commit"

# Crea repository GitHub
# https://github.com/new → "mayanalytics-frontend"

# Push
git remote add origin https://github.com/your-username/mayanalytics-frontend.git
git branch -M main
git push -u origin main
```

#### 2. **Crea App Amplify**

**Via AWS Console**:
```
1. Vai a AWS Amplify Console
   https://console.aws.amazon.com/amplify/

2. Click "New app" → "Host web app"

3. Seleziona "GitHub"
   - Autorizza AWS Amplify ad accedere GitHub
   - Seleziona repository "mayanalytics-frontend"
   - Seleziona branch "main"

4. App settings:
   Name: maya-analytics-frontend
   Environment: prod
   
5. Build settings (auto-detected da amplify.yml):
   ✅ amplify.yml trovato
   
6. Advanced settings:
   Environment variables:
   - NEXT_PUBLIC_API_URL = https://78jt5iyn1f.execute-api.eu-central-1.amazonaws.com/Prod
   - NEXT_PUBLIC_COGNITO_USER_POOL_ID = eu-central-1_eIs0HT7aN
   - NEXT_PUBLIC_COGNITO_CLIENT_ID = 41erklu7iorpilb2dn98avf76f
   - NEXT_PUBLIC_COGNITO_REGION = eu-central-1

7. Click "Save and deploy"
```

**Via AWS CLI**:
```bash
# Crea app
aws amplify create-app \
    --name maya-analytics-frontend \
    --repository https://github.com/your-username/mayanalytics-frontend \
    --platform WEB \
    --oauth-token ghp_YOUR_GITHUB_TOKEN \
    --region eu-central-1

# Crea branch
aws amplify create-branch \
    --app-id YOUR_APP_ID \
    --branch-name main \
    --enable-auto-build \
    --region eu-central-1

# Aggiungi environment variables
aws amplify update-app \
    --app-id YOUR_APP_ID \
    --environment-variables \
        NEXT_PUBLIC_API_URL=https://78jt5iyn1f.execute-api.eu-central-1.amazonaws.com/Prod,\
        NEXT_PUBLIC_COGNITO_USER_POOL_ID=eu-central-1_eIs0HT7aN,\
        NEXT_PUBLIC_COGNITO_CLIENT_ID=41erklu7iorpilb2dn98avf76f,\
        NEXT_PUBLIC_COGNITO_REGION=eu-central-1 \
    --region eu-central-1

# Start build
aws amplify start-job \
    --app-id YOUR_APP_ID \
    --branch-name main \
    --job-type RELEASE \
    --region eu-central-1
```

#### 3. **Monitora Build**

**Build Progress**:
```
Amplify Console → maya-analytics-frontend → main

Build Log:
┌─────────────────────────────────────┐
│  # Provision (1 min)                │
│  ✅ Container provisioned           │
│                                     │
│  # Build (3-5 min)                  │
│  ✅ npm ci                          │
│  ✅ npm run build                   │
│                                     │
│  # Deploy (1 min)                   │
│  ✅ Deploy to CloudFront            │
│                                     │
│  # Verify (30s)                     │
│  ✅ Health check passed             │
└─────────────────────────────────────┘

App URL: https://main.d1234abcdefg.amplifyapp.com
```

**Troubleshooting Build**:
```bash
# Se build fallisce, verifica log:
aws amplify get-job \
    --app-id YOUR_APP_ID \
    --branch-name main \
    --job-id JOB_ID \
    --region eu-central-1

# Errori comuni:
# 1. Environment variables mancanti
#    → Aggiungi in Amplify Console → Environment variables

# 2. Build timeout
#    → Aumenta timeout in amplify.yml

# 3. Out of memory
#    → Riduci bundle size o usa custom build image
```

#### 4. **Custom Domain** (Optional)

**Aggiungi Dominio Custom**:
```
Amplify Console → Domain management → Add domain

1. Domain: mayaanalytics.com
2. Amplify crea automaticamente certificato SSL (ACM)
3. Aggiungi record DNS:
   
   Type: CNAME
   Name: www
   Value: main.d1234abcdefg.amplifyapp.com
   
   Type: ANAME/ALIAS (if supported by DNS)
   Name: @
   Value: main.d1234abcdefg.amplifyapp.com

4. Verifica DNS propagation (può richiedere 24-48h)
5. Certificato SSL automaticamente provisionato
```

**Redirect www → root**:
```
Amplify Console → Rewrites and redirects

Source: https://www.mayaanalytics.com
Target: https://mayaanalytics.com
Type: 301 - Permanent Redirect
```

### CI/CD Automatico

**Amplify CI/CD**:
```yaml
# amplify.yml (già configurato)
version: 1
applications:
  - appRoot: Deploy/frontend
    frontend:
      phases:
        preBuild:
          commands:
            - npm ci  # Installa dipendenze
        build:
          commands:
            - npm run build  # Build Next.js
      artifacts:
        baseDirectory: .next
        files:
          - '**/*'
      cache:
        paths:
          - node_modules/**/*
          - .next/cache/**/*
```

**Workflow**:
```
1. Developer fa git push su branch main
2. Amplify rileva commit (webhook GitHub)
3. Trigger build automatico:
   - Clona repository
   - Installa dependencies (npm ci)
   - Build app (npm run build)
   - Deploy su CloudFront
   - Invalidate cache CDN
4. App aggiornata (downtime zero!)
5. Notifica Slack/Email (opzionale)
```

**Branch Deployments**:
```
# Deploy branch develop separato
main → https://main.d1234abcdefg.amplifyapp.com (production)
develop → https://develop.d1234abcdefg.amplifyapp.com (staging)
feature/x → https://feature-x.d1234abcdefg.amplifyapp.com (preview)

# Configure in Amplify Console:
# General → Branch → Add branch
```

### Monitoring & Troubleshooting

#### 1. **CloudWatch Dashboards**

**Crea Dashboard Custom**:
```bash
# Via AWS Console:
CloudWatch → Dashboards → Create dashboard → "maya-analytics-prod"

# Aggiungi widgets:
# 1. Lambda Invocations (all 3 functions)
# 2. Lambda Errors
# 3. Lambda Duration
# 4. API Gateway 4XX/5XX errors
# 5. API Gateway Latency
# 6. DynamoDB Read/Write Capacity
# 7. Cognito Sign In Successes/Failures
```

#### 2. **CloudWatch Alarms**

**Alarms Critici**:
```bash
# 1. Lambda Errors > 5 in 5 minutes
aws cloudwatch put-metric-alarm \
    --alarm-name maya-lambda-errors-high \
    --alarm-description "Lambda errors above threshold" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --statistic Sum \
    --period 300 \
    --threshold 5 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --alarm-actions arn:aws:sns:eu-central-1:ACCOUNT_ID:alerts

# 2. API Gateway 5XX > 10 in 5 minutes
aws cloudwatch put-metric-alarm \
    --alarm-name maya-api-5xx-high \
    --metric-name 5XXError \
    --namespace AWS/ApiGateway \
    --statistic Sum \
    --period 300 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1

# 3. Report Generator Duration > 280s (timeout 301s)
aws cloudwatch put-metric-alarm \
    --alarm-name maya-report-generator-timeout-risk \
    --metric-name Duration \
    --namespace AWS/Lambda \
    --statistic Maximum \
    --period 300 \
    --threshold 280000 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1
```

#### 3. **Logs Analysis**

**Query CloudWatch Logs Insights**:
```sql
-- Trova tutti gli errori ultimi 24h
fields @timestamp, @message
| filter @message like /ERROR|Exception/
| sort @timestamp desc
| limit 100

-- Lambda duration statistics
fields @duration
| stats avg(@duration), max(@duration), min(@duration)
| filter @type = "REPORT"

-- Report generation successes
fields @timestamp, user_id, report_type
| filter @message like /Report sent successfully/
| count(*) by bin(5m)

-- Failed report generations
fields @timestamp, user_id, error
| filter @message like /Error generating report/
| sort @timestamp desc
```

#### 4. **X-Ray Tracing** (Optional)

**Abilita X-Ray**:
```yaml
# template.yaml
Globals:
  Function:
    Tracing: Active

# Rideploy
sam deploy
```

**Visualizza Traces**:
```
AWS X-Ray Console → Traces

Esempio trace:
┌─────────────────────────────────────────┐
│  API Gateway (15ms)                     │
│    └─ ApiFunction (120ms)               │
│       ├─ DynamoDB GetItem (5ms)         │
│       ├─ Lambda Invoke ReportGen (2.5s) │
│       │  ├─ HTTP Request XML (800ms)    │
│       │  ├─ Bedrock InvokeModel (1.2s)  │
│       │  └─ Lambda Invoke Email (300ms) │
│       │     └─ SES SendEmail (250ms)    │
│       └─ DynamoDB PutItem (8ms)         │
│                                         │
│  Total Duration: 2.65s                  │
└─────────────────────────────────────────┘
```

### Rollback & Disaster Recovery

#### 1. **Rollback CloudFormation Stack**

```bash
# Lista stack updates
aws cloudformation describe-stack-events \
    --stack-name maya-analytics-prod \
    --region eu-central-1

# Rollback a versione precedente
aws cloudformation cancel-update-stack \
    --stack-name maya-analytics-prod \
    --region eu-central-1

# Oppure elimina e ricrea da versione precedente
aws cloudformation delete-stack \
    --stack-name maya-analytics-prod

# Rideploy versione precedente
sam deploy --parameter-overrides Environment=prod
```

#### 2. **Rollback Amplify Frontend**

```bash
# Lista deployments
aws amplify list-jobs \
    --app-id YOUR_APP_ID \
    --branch-name main \
    --region eu-central-1

# Rollback a job precedente
aws amplify start-job \
    --app-id YOUR_APP_ID \
    --branch-name main \
    --job-type RELEASE \
    --commit-id PREVIOUS_COMMIT_SHA \
    --region eu-central-1
```

#### 3. **Backup DynamoDB**

**On-Demand Backup**:
```bash
# Backup manuale
aws dynamodb create-backup \
    --table-name maya-users-prod \
    --backup-name maya-users-backup-$(date +%Y%m%d) \
    --region eu-central-1

# Lista backups
aws dynamodb list-backups \
    --table-name maya-users-prod

# Restore da backup
aws dynamodb restore-table-from-backup \
    --target-table-name maya-users-prod-restored \
    --backup-arn arn:aws:dynamodb:eu-central-1:ACCOUNT_ID:table/maya-users-prod/backup/BACKUP_ID
```

**Point-in-Time Recovery (PITR)** (Recommended):
```bash
# Abilita PITR
aws dynamodb update-continuous-backups \
    --table-name maya-users-prod \
    --point-in-time-recovery-specification PointInTimeRecoveryEnabled=true

# Restore a timestamp specifico
aws dynamodb restore-table-to-point-in-time \
    --source-table-name maya-users-prod \
    --target-table-name maya-users-prod-restored \
    --restore-date-time 2024-01-15T10:30:00Z
```

### Costi Stimati

**Monthly Cost Breakdown** (Production - 100 users, 2000 reports/month):

| Servizio | Utilizzo | Costo Mensile |
|----------|----------|--------------|
| **Lambda** | ~50,000 invocations, 1GB-s | ~$5 |
| **API Gateway** | 50,000 requests | ~$0.05 |
| **DynamoDB** | Pay-per-request, ~100k ops | ~$1.25 |
| **Cognito** | 100 MAU (Monthly Active Users) | Free (< 50k) |
| **Bedrock (Claude)** | 2000 invocations × 2k tokens | ~$60 |
| **SES** | 2000 emails | ~$0.20 |
| **CloudWatch** | Logs 5GB, Metrics standard | ~$2 |
| **Amplify Hosting** | 100GB bandwidth, build minutes | ~$5 |
| **Total** | | **~$73/month** |

**Scaling Costs**:
- 1,000 users, 20k reports/month: ~$600/month (mostly Bedrock)
- 10,000 users, 200k reports/month: ~$6,000/month

**Cost Optimization**:
- ✅ DynamoDB on-demand (no provisioned capacity waste)
- ✅ Lambda timeout ottimizzati
- ✅ S3 lifecycle policies (not used yet)
- ✅ CloudWatch Logs retention 30 giorni (riduci se serve)
- ⚠️ Bedrock è il costo principale (considera caching insights simili)

---

## 📞 Support

**Developed by**: Neuralect  
**Contact**: info@neuralect.it  
**Website**: https://neuralect.it

---

## 📝 License

Proprietary - © 2024 Neuralect. All rights reserved.

