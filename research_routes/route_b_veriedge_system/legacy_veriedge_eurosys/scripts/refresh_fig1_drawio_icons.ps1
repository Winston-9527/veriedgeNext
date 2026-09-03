$ErrorActionPreference = 'Stop'

$diagramPath = Join-Path $PSScriptRoot '..\figures\fig_system_model_workflow_recreated.drawio'
$diagramPath = (Resolve-Path $diagramPath).Path

$doc = New-Object System.Xml.XmlDocument
$doc.PreserveWhitespace = $true
$doc.Load($diagramPath)
$root = $doc.SelectSingleNode('//mxGraphModel/root')

$iconBodies = @{
  user = '<path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/>'
  fileText = '<path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z"/><path d="M14 2v5h5"/><path d="M9 13h6"/><path d="M9 17h6"/><path d="M9 9h1"/>'
  lock = '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 15v2"/>'
  key = '<circle cx="7.5" cy="14.5" r="3.5"/><path d="M10.2 12l8.8-8.8"/><path d="M15 6.2l2.8 2.8"/><path d="M13.1 8.1l2 2"/>'
  shield = '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M9 12l2 2 4-5"/>'
  gear = '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1A2 2 0 1 1 4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1A2 2 0 1 1 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3h.1A1.7 1.7 0 0 0 10 3.1V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6h.1a1.7 1.7 0 0 0 1.9-.3l.1-.1A2 2 0 1 1 19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9v.1A1.7 1.7 0 0 0 21 10h.1a2 2 0 1 1 0 4H21a1.7 1.7 0 0 0-1.6 1z"/>'
  search = '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.4-4.4"/>'
  users = '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>'
  grid = '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>'
  clipboard = '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4.5A2.5 2.5 0 0 1 11.5 2h1A2.5 2.5 0 0 1 15 4.5V6H9z"/><path d="M9 11h6"/><path d="M9 15h6"/>'
  server = '<rect x="4" y="4" width="16" height="6" rx="2"/><rect x="4" y="14" width="16" height="6" rx="2"/><path d="M8 7h.01"/><path d="M8 17h.01"/><path d="M12 7h4"/><path d="M12 17h4"/>'
  warning = '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v5"/><path d="M12 17h.01"/>'
  link = '<path d="M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1"/><path d="M14 11a5 5 0 0 0-7.1 0l-2 2a5 5 0 0 0 7.1 7.1l1.1-1.1"/>'
  wallet = '<path d="M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a3 3 0 0 1 3-3h12v4"/><path d="M16 13h.01"/>'
  checklist = '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 7h6"/><path d="m8.5 12 1.5 1.5 3.5-3.5"/><path d="M9 17h6"/>'
  bank = '<path d="M3 21h18"/><path d="M5 10h14"/><path d="M6 10v8"/><path d="M10 10v8"/><path d="M14 10v8"/><path d="M18 10v8"/><path d="M12 3 3 8h18z"/>'
  database = '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>'
  scales = '<path d="M12 3v18"/><path d="M5 6h14"/><path d="M6 6l-3 7h6z"/><path d="M18 6l-3 7h6z"/><path d="M4 20h16"/>'
}

function Get-Cell([string] $id) {
  return $doc.SelectSingleNode("//mxCell[@id='$id']")
}

function Get-IconStyle([string] $iconName, [string] $color) {
  if (-not $iconBodies.ContainsKey($iconName)) {
    throw "Unknown icon '$iconName'"
  }
  $body = $iconBodies[$iconName]
  $svg = "<svg xmlns=""http://www.w3.org/2000/svg"" viewBox=""0 0 24 24"" fill=""none"" stroke=""#$color"" stroke-width=""2.2"" stroke-linecap=""round"" stroke-linejoin=""round"">$body</svg>"
  $b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($svg))
  return "shape=image;html=1;verticalLabelPosition=bottom;verticalAlign=top;imageAspect=0;aspect=fixed;image=data:image/svg+xml;base64,$b64;"
}

function Set-Geometry([System.Xml.XmlElement] $cell, [double] $x, [double] $y, [double] $w, [double] $h) {
  $geom = $cell.SelectSingleNode('mxGeometry')
  if (-not $geom) {
    $geom = $doc.CreateElement('mxGeometry')
    [void] $cell.AppendChild($geom)
  }
  $geom.SetAttribute('x', [string] $x)
  $geom.SetAttribute('y', [string] $y)
  $geom.SetAttribute('width', [string] $w)
  $geom.SetAttribute('height', [string] $h)
  $geom.SetAttribute('as', 'geometry')
}

function Set-Icon([string] $id, [string] $iconName, [string] $color, [double] $x, [double] $y, [double] $w, [double] $h) {
  $cell = Get-Cell $id
  if (-not $cell) {
    $cell = $doc.CreateElement('mxCell')
    $cell.SetAttribute('id', $id)
    $cell.SetAttribute('parent', '1')
    [void] $root.AppendChild($cell)
  }
  $cell.SetAttribute('style', (Get-IconStyle $iconName $color))
  $cell.SetAttribute('value', '')
  $cell.SetAttribute('vertex', '1')
  if ($cell.HasAttribute('edge')) {
    $cell.RemoveAttribute('edge')
  }
  Set-Geometry $cell $x $y $w $h
}

function Remove-Cell([string] $id) {
  $cell = Get-Cell $id
  if ($cell) {
    [void] $cell.ParentNode.RemoveChild($cell)
  }
}

function Move-Cell([string] $id, [double] $x, [double] $y, [double] $w, [double] $h) {
  $cell = Get-Cell $id
  if (-not $cell) {
    throw "Missing cell '$id'"
  }
  Set-Geometry $cell $x $y $w $h
}

# Remove the old two-shape filled person mark and replace it with one line icon.
Remove-Cell 'req-body'

# Requester icons.
Set-Icon 'req-head' 'user' '0B49B5' 60 30 62 62
Set-Icon 'req-icon-doc' 'fileText' '111827' 75 118 44 44
Set-Icon 'req-icon-lock' 'lock' '111827' 75 188 44 44
Set-Icon 'req-icon-key' 'key' '111827' 75 258 44 44
Set-Icon 'req-icon-shield' 'shield' '0B49B5' 75 322 44 44

# Orchestrator icons.
Set-Icon 'orch-gear' 'gear' '7A3B0A' 520 36 58 58
Set-Icon 'orch-icon-search' 'search' '111827' 542 112 38 38
Set-Icon 'orch-icon-group' 'users' '111827' 542 172 38 38
Set-Icon 'orch-icon-grid' 'grid' '111827' 542 232 38 38
Set-Icon 'orch-icon-commit' 'clipboard' '111827' 542 292 38 38
Set-Icon 'orch-note-lock' 'lock' '7A3B0A' 535 338 30 30

# Provider icons.
Set-Icon 'prov-server-icon' 'server' '0A6B16' 1010 35 56 56
Set-Icon 'p1-server' 'server' '168321' 1033 168 46 34
Set-Icon 'p2-server' 'server' '168321' 1176 168 46 34
Set-Icon 'p3-server' 'server' 'C81818' 1321 168 46 34
Set-Icon 'p3-warning' 'warning' 'C81818' 1362 178 36 36
Set-Icon 'p4-server-icon' 'server' '4B5563' 1068 334 30 30
Set-Icon 'p5-server-icon' 'server' '4B5563' 1208 334 30 30
Move-Cell 'p4-label' 1098 333 45 34
Move-Cell 'p5-label' 1238 333 45 34

# Ledger icons.
Set-Icon 'ledger-icon' 'link' '3E1593' 270 650 54 54
Set-Icon 'ledger-item1-icon' 'fileText' '3E1593' 260 723 36 36
Set-Icon 'ledger-item2-icon' 'wallet' '3E1593' 430 723 36 36
Set-Icon 'ledger-item3-icon' 'checklist' '3E1593' 570 723 36 36
Set-Icon 'ledger-item4-icon' 'bank' '3E1593' 720 723 36 36

# Data store and verifier icons.
Set-Icon 'store-icon' 'database' '0B49B5' 1010 655 52 52
Set-Icon 'store-lock' 'lock' '0B49B5' 1020 723 36 36
Set-Icon 'store-cylinder-small' 'database' '0B49B5' 1248 721 40 40
Set-Icon 'verifier-icon' 'scales' '3E1593' 725 518 54 54

$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $true
$settings.NewLineChars = "`n"
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$writer = [System.Xml.XmlWriter]::Create($diagramPath, $settings)
try {
  $doc.Save($writer)
} finally {
  $writer.Close()
}

Write-Host "Updated unified SVG icons in $diagramPath"
