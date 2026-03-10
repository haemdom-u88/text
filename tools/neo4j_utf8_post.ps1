$ErrorActionPreference = 'Stop'

$payload = @{
  extraction = @{
    nodes = @(
      @{ id = "中文节点A"; name = "中文节点A"; type = "Concept" }
      @{ id = "中文节点B"; name = "中文节点B"; type = "Concept" }
    )
    edges = @(
      @{ source = "中文节点A"; target = "中文节点B"; type = "PREREQUISITE_OF"; confidence = 0.9; reasoning = "测试" }
    )
  }
} | ConvertTo-Json -Depth 5

Add-Type -AssemblyName System.Net.Http
$client = New-Object System.Net.Http.HttpClient
try {
  $content = New-Object System.Net.Http.StringContent($payload, [System.Text.Encoding]::UTF8, "application/json")
  $resp = $client.PostAsync("http://127.0.0.1:5000/api/generate_graph", $content).GetAwaiter().GetResult()
  $resp.Content.ReadAsStringAsync().Result
} finally {
  $client.Dispose()
}
