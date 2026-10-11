// Week 11: observability for the hosted API, kept inside the free allowances.
//
//   * A Log Analytics workspace (pay-as-you-go; the first 5 GB a month per billing account are free, and
//     this service sends kilobytes). A DAILY CAP makes the worst case a bounded number, not a surprise.
//   * Application Insights, workspace-based, with key authentication DISABLED: the app signs in with its
//     own identity ("Monitoring Metrics Publisher" on the component), so there is no key to leak.
//   * A workbook (the dashboard): workbooks have no charge of their own.
//   * Two metric alert rules (average latency, failed requests). The first 10 monitored metric time
//     series and 1,000 alert emails a month are free. Percentile alerts (p95) are not possible as metric
//     alerts, and a log-search alert for them would be a paid rule, so p95 is on the dashboard only.
//
// Prices and allowances: Microsoft's Azure Monitor pricing page (fetched 2026-10-12); the per-unit
// prices are masked on that page, so only the free quantities above are relied on.

targetScope = 'resourceGroup'

@description('Short lowercase prefix for resource names.')
@maxLength(10)
param namePrefix string = 'payrag'

param location string = resourceGroup().location

@description('Object ID of the web app identity that sends telemetry.')
param appPrincipalId string

@description('Where alert emails go. Empty: alerts still fire and show in the portal, but nobody is emailed.')
param alertEmail string = ''

@description('Hard cap on log data per day, in GB, as text (Bicep has no decimal type). 0.1 GB is far above what this service sends.')
param dailyCapGb string = '0.1'

@description('Alert when the average response time of POST /ask over 15 minutes is above this (ms).')
param latencyThresholdMs int = 8000

@description('Alert when this many requests fail within 15 minutes.')
param failedRequestsThreshold int = 3

var unique = uniqueString(resourceGroup().id)
var workspaceName = '${namePrefix}-law-${take(unique, 8)}'
var componentName = '${namePrefix}-ai-${take(unique, 8)}'
var roleMonitoringMetricsPublisher = '3913510d-42f4-4e42-8a64-420c390055eb'

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30 // 31 days of Analytics retention are included in the ingestion price
    workspaceCapping: {
      dailyQuotaGb: json(dailyCapGb)
    }
  }
}

resource component 'Microsoft.Insights/components@2020-02-02' = {
  name: componentName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Flow_Type: 'Bluefield'
    Request_Source: 'rest'
    WorkspaceResourceId: workspace.id
    DisableLocalAuth: true // Entra ID only: telemetry without an identity is rejected
    DisableIpMasking: false
  }
}

resource appPublishesTelemetry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: component
  name: guid(component.id, appPrincipalId, roleMonitoringMetricsPublisher)
  properties: {
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleMonitoringMetricsPublisher)
  }
}

resource dashboard 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: guid(resourceGroup().id, 'payrag-operations-workbook')
  location: location
  kind: 'shared'
  properties: {
    displayName: 'Payments assistant: live operations'
    category: 'workbook'
    sourceId: component.id
    version: '1.0'
    serializedData: replace(loadTextContent('week11-workbook.json'), '__APP_INSIGHTS_ID__', component.id)
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${namePrefix}-alerts'
  location: 'global'
  properties: {
    groupShortName: 'payrag'
    enabled: true
    emailReceivers: empty(alertEmail)
      ? []
      : [
          {
            name: 'owner'
            emailAddress: alertEmail
            useCommonAlertSchema: true
          }
        ]
  }
}

resource slowAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-slow-responses'
  location: 'global'
  properties: {
    description: 'Average response time of the API is high (metric alerts cannot use percentiles).'
    severity: 2
    enabled: true
    scopes: [component.id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'slow'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/duration'
          operator: 'GreaterThan'
          threshold: latencyThresholdMs
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [{ actionGroupId: actionGroup.id }]
  }
}

resource failedAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-failed-requests'
  location: 'global'
  properties: {
    description: 'Several requests failed (HTTP 5xx or an unhandled error) within 15 minutes.'
    severity: 1
    enabled: true
    scopes: [component.id]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          criterionType: 'StaticThresholdCriterion'
          name: 'failed'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/failed'
          operator: 'GreaterThanOrEqual'
          threshold: failedRequestsThreshold
          timeAggregation: 'Count'
        }
      ]
    }
    actions: [{ actionGroupId: actionGroup.id }]
  }
}

output componentName string = component.name
output connectionString string = component.properties.ConnectionString
output workspaceName string = workspace.name
output dashboardId string = dashboard.id
