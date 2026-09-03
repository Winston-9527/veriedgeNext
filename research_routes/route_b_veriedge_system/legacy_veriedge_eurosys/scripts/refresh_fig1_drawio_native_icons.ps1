$ErrorActionPreference = 'Stop'

$diagramPath = Join-Path $PSScriptRoot '..\figures\fig_system_model_workflow_recreated.drawio'
$diagramPath = (Resolve-Path $diagramPath).Path

$doc = New-Object System.Xml.XmlDocument
$doc.PreserveWhitespace = $true
$doc.Load($diagramPath)
$root = $doc.SelectSingleNode('//mxGraphModel/root')

function Remove-ByXPath([string] $xpath) {
  $nodes = @($doc.SelectNodes($xpath))
  foreach ($node in $nodes) {
    [void] $node.ParentNode.RemoveChild($node)
  }
}

function Add-Vertex([string] $id, [string] $style, [double] $x, [double] $y, [double] $w, [double] $h, [string] $value = '') {
  $cell = $doc.CreateElement('mxCell')
  $cell.SetAttribute('id', $id)
  $cell.SetAttribute('parent', '1')
  $cell.SetAttribute('style', $style)
  $cell.SetAttribute('value', $value)
  $cell.SetAttribute('vertex', '1')
  $geom = $doc.CreateElement('mxGeometry')
  $geom.SetAttribute('x', [string] $x)
  $geom.SetAttribute('y', [string] $y)
  $geom.SetAttribute('width', [string] $w)
  $geom.SetAttribute('height', [string] $h)
  $geom.SetAttribute('as', 'geometry')
  [void] $cell.AppendChild($geom)
  [void] $root.AppendChild($cell)
}

function Add-Line([string] $id, [double] $x1, [double] $y1, [double] $x2, [double] $y2, [string] $color, [double] $width = 2.2) {
  $cell = $doc.CreateElement('mxCell')
  $cell.SetAttribute('id', $id)
  $cell.SetAttribute('parent', '1')
  $cell.SetAttribute('style', "endArrow=none;startArrow=none;html=1;rounded=1;strokeColor=#$color;strokeWidth=$width;")
  $cell.SetAttribute('value', '')
  $cell.SetAttribute('edge', '1')
  $geom = $doc.CreateElement('mxGeometry')
  $geom.SetAttribute('relative', '1')
  $geom.SetAttribute('as', 'geometry')
  $src = $doc.CreateElement('mxPoint')
  $src.SetAttribute('x', [string] $x1)
  $src.SetAttribute('y', [string] $y1)
  $src.SetAttribute('as', 'sourcePoint')
  $dst = $doc.CreateElement('mxPoint')
  $dst.SetAttribute('x', [string] $x2)
  $dst.SetAttribute('y', [string] $y2)
  $dst.SetAttribute('as', 'targetPoint')
  [void] $geom.AppendChild($src)
  [void] $geom.AppendChild($dst)
  [void] $cell.AppendChild($geom)
  [void] $root.AppendChild($cell)
}

function Style-Stroke([string] $color, [double] $width = 2.2, [string] $shape = '') {
  $shapePart = if ($shape) { "shape=$shape;" } else { '' }
  return "${shapePart}rounded=1;whiteSpace=wrap;html=1;arcSize=18;fillColor=none;strokeColor=#$color;strokeWidth=$width;"
}

function Style-Fill([string] $color, [string] $shape = '') {
  $shapePart = if ($shape) { "shape=$shape;" } else { '' }
  return "${shapePart}rounded=1;whiteSpace=wrap;html=1;arcSize=18;fillColor=#$color;strokeColor=#$color;strokeWidth=1;"
}

function Icon-User([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-head" (Style-Stroke $c 2.4 'ellipse') ($x + 20) $y 22 22
  Add-Vertex "$p-body" (Style-Stroke $c 2.4) ($x + 10) ($y + 30) 42 28
}

function Icon-File([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-page" (Style-Stroke $c) ($x + 7) ($y + 3) 29 37
  Add-Line "$p-fold1" ($x + 27) ($y + 3) ($x + 36) ($y + 12) $c
  Add-Line "$p-fold2" ($x + 27) ($y + 3) ($x + 27) ($y + 12) $c
  Add-Line "$p-l1" ($x + 14) ($y + 20) ($x + 30) ($y + 20) $c
  Add-Line "$p-l2" ($x + 14) ($y + 27) ($x + 30) ($y + 27) $c
  Add-Line "$p-l3" ($x + 14) ($y + 34) ($x + 24) ($y + 34) $c
}

function Icon-Lock([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-body" (Style-Stroke $c) ($x + 8) ($y + 19) 30 22
  Add-Line "$p-left" ($x + 15) ($y + 19) ($x + 15) ($y + 12) $c
  Add-Line "$p-top" ($x + 15) ($y + 12) ($x + 31) ($y + 12) $c
  Add-Line "$p-right" ($x + 31) ($y + 12) ($x + 31) ($y + 19) $c
  Add-Line "$p-keyhole" ($x + 23) ($y + 29) ($x + 23) ($y + 34) $c
}

function Icon-Key([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-ring" (Style-Stroke $c) ($x + 3) ($y + 18) 16 16
  Add-Line "$p-stem" ($x + 18) ($y + 22) ($x + 39) ($y + 5) $c
  Add-Line "$p-tooth1" ($x + 31) ($y + 12) ($x + 36) ($y + 17) $c
  Add-Line "$p-tooth2" ($x + 27) ($y + 16) ($x + 31) ($y + 20) $c
}

function Icon-Shield([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-shape" "shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#$c;strokeWidth=2.2;" ($x + 6) ($y + 3) 32 38
  Add-Line "$p-check1" ($x + 15) ($y + 23) ($x + 20) ($y + 28) $c
  Add-Line "$p-check2" ($x + 20) ($y + 28) ($x + 30) ($y + 16) $c
}

function Icon-Gear([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-outer" (Style-Stroke $c 2.4 'ellipse') ($x + 7) ($y + 7) 44 44
  Add-Vertex "$p-inner" (Style-Stroke $c 2.4 'ellipse') ($x + 22) ($y + 22) 14 14
  Add-Line "$p-n" ($x + 29) ($y + 0) ($x + 29) ($y + 9) $c 3
  Add-Line "$p-s" ($x + 29) ($y + 49) ($x + 29) ($y + 58) $c 3
  Add-Line "$p-w" ($x + 0) ($y + 29) ($x + 9) ($y + 29) $c 3
  Add-Line "$p-e" ($x + 49) ($y + 29) ($x + 58) ($y + 29) $c 3
  Add-Line "$p-nw" ($x + 9) ($y + 9) ($x + 16) ($y + 16) $c 3
  Add-Line "$p-ne" ($x + 49) ($y + 9) ($x + 42) ($y + 16) $c 3
  Add-Line "$p-sw" ($x + 9) ($y + 49) ($x + 16) ($y + 42) $c 3
  Add-Line "$p-se" ($x + 49) ($y + 49) ($x + 42) ($y + 42) $c 3
}

function Icon-Search([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-circle" (Style-Stroke $c) ($x + 5) ($y + 4) 24 24
  Add-Line "$p-handle" ($x + 25) ($y + 25) ($x + 38) ($y + 38) $c
}

function Icon-Users([string] $p, [double] $x, [double] $y, [string] $c) {
  Icon-User "$p-a" ($x + 2) ($y + 2) $c
  Add-Vertex "$p-b-head" (Style-Stroke $c 2.2 'ellipse') ($x + 24) ($y + 5) 13 13
  Add-Vertex "$p-b-body" (Style-Stroke $c 2.2) ($x + 20) ($y + 25) 24 15
}

function Icon-Grid([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-a" (Style-Stroke $c) ($x + 3) ($y + 3) 14 14
  Add-Vertex "$p-b" (Style-Stroke $c) ($x + 23) ($y + 3) 14 14
  Add-Vertex "$p-c" (Style-Stroke $c) ($x + 3) ($y + 23) 14 14
  Add-Vertex "$p-d" (Style-Stroke $c) ($x + 23) ($y + 23) 14 14
}

function Icon-Clipboard([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-board" (Style-Stroke $c) ($x + 7) ($y + 5) 28 34
  Add-Vertex "$p-clip" (Style-Stroke $c) ($x + 14) ($y + 2) 14 8
  Add-Line "$p-l1" ($x + 13) ($y + 18) ($x + 29) ($y + 18) $c
  Add-Line "$p-l2" ($x + 13) ($y + 26) ($x + 29) ($y + 26) $c
}

function Icon-Server([string] $p, [double] $x, [double] $y, [string] $c, [double] $s = 1.0) {
  Add-Vertex "$p-top" (Style-Stroke $c) $x $y (38 * $s) (14 * $s)
  Add-Vertex "$p-bot" (Style-Stroke $c) $x ($y + 19 * $s) (38 * $s) (14 * $s)
  Add-Vertex "$p-dot1" (Style-Fill $c 'ellipse') ($x + 6 * $s) ($y + 5 * $s) (3 * $s) (3 * $s)
  Add-Vertex "$p-dot2" (Style-Fill $c 'ellipse') ($x + 6 * $s) ($y + 24 * $s) (3 * $s) (3 * $s)
  Add-Line "$p-line1" ($x + 16 * $s) ($y + 7 * $s) ($x + 31 * $s) ($y + 7 * $s) $c 2
  Add-Line "$p-line2" ($x + 16 * $s) ($y + 26 * $s) ($x + 31 * $s) ($y + 26 * $s) $c 2
}

function Icon-Warning([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-tri" "shape=triangle;direction=north;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#$c;strokeWidth=2.2;" ($x + 4) ($y + 2) 28 30
  Add-Line "$p-stem" ($x + 18) ($y + 11) ($x + 18) ($y + 21) $c 2.2
  Add-Vertex "$p-dot" (Style-Fill $c 'ellipse') ($x + 16.5) ($y + 25) 3 3
}

function Icon-Link([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-a" (Style-Stroke $c) ($x + 5) ($y + 18) 24 14
  Add-Vertex "$p-b" (Style-Stroke $c) ($x + 24) ($y + 8) 24 14
  Add-Line "$p-mid" ($x + 22) ($y + 22) ($x + 31) ($y + 18) $c
}

function Icon-Wallet([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-main" (Style-Stroke $c) ($x + 2) ($y + 8) 36 25
  Add-Vertex "$p-flap" (Style-Stroke $c) ($x + 23) ($y + 16) 18 10
  Add-Vertex "$p-dot" (Style-Fill $c 'ellipse') ($x + 31) ($y + 20) 3 3
}

function Icon-Checklist([string] $p, [double] $x, [double] $y, [string] $c) {
  Icon-Clipboard "$p-cb" $x $y $c
  Add-Line "$p-check1" ($x + 13) ($y + 26) ($x + 17) ($y + 30) $c
  Add-Line "$p-check2" ($x + 17) ($y + 30) ($x + 26) ($y + 20) $c
}

function Icon-Bank([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Vertex "$p-roof" "shape=triangle;direction=north;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#$c;strokeWidth=2.2;" ($x + 4) ($y + 3) 32 16
  Add-Line "$p-base1" ($x + 3) ($y + 19) ($x + 37) ($y + 19) $c
  Add-Line "$p-base2" ($x + 3) ($y + 36) ($x + 37) ($y + 36) $c
  foreach ($i in 0..2) {
    $cx = $x + 9 + ($i * 10)
    Add-Line "$p-col$i" $cx ($y + 20) $cx ($y + 35) $c
  }
}

function Icon-Database([string] $p, [double] $x, [double] $y, [string] $c, [double] $w, [double] $h) {
  Add-Vertex "$p-db" "shape=cylinder;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=12;fillColor=none;strokeColor=#$c;strokeWidth=2.2;" $x $y $w $h
}

function Icon-Scales([string] $p, [double] $x, [double] $y, [string] $c) {
  Add-Line "$p-post" ($x + 27) ($y + 4) ($x + 27) ($y + 47) $c
  Add-Line "$p-arm" ($x + 8) ($y + 14) ($x + 46) ($y + 14) $c
  Add-Vertex "$p-left-pan" "shape=triangle;direction=south;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#$c;strokeWidth=2.2;" ($x + 3) ($y + 20) 18 18
  Add-Vertex "$p-right-pan" "shape=triangle;direction=south;whiteSpace=wrap;html=1;fillColor=none;strokeColor=#$c;strokeWidth=2.2;" ($x + 33) ($y + 20) 18 18
  Add-Line "$p-base" ($x + 14) ($y + 48) ($x + 40) ($y + 48) $c
}

# Clear previous broken SVG image cells and any previously generated native icons.
Remove-ByXPath "//mxCell[contains(@style, 'shape=image')]"
Remove-ByXPath "//mxCell[starts-with(@id, 'native-')]"

# Add icons as native draw.io geometry.
Icon-User      'native-req-user'       60   30  '0B49B5'
Icon-File      'native-req-file'       75   118 '111827'
Icon-Lock      'native-req-lock'       75   188 '111827'
Icon-Key       'native-req-key'        75   258 '111827'
Icon-Shield    'native-req-shield'     75   322 '0B49B5'

Icon-Gear      'native-orch-gear'      520  36  '7A3B0A'
Icon-Search    'native-orch-search'    542  112 '111827'
Icon-Users     'native-orch-users'     542  172 '111827'
Icon-Grid      'native-orch-grid'      542  232 '111827'
Icon-Clipboard 'native-orch-clip'      542  292 '111827'
Icon-Lock      'native-orch-lock'      535  338 '7A3B0A'

Icon-Server    'native-prov-pool'      1018 38  '0A6B16' 1.15
Icon-Server    'native-p1'             1037 169 '168321' 1.00
Icon-Server    'native-p2'             1180 169 '168321' 1.00
Icon-Server    'native-p3'             1325 169 'C81818' 1.00
Icon-Warning   'native-p3-warn'        1362 178 'C81818'
Icon-Server    'native-p4'             1065 335 '4B5563' 0.75
Icon-Server    'native-p5'             1205 335 '4B5563' 0.75

Icon-Link      'native-ledger-link'    270  654 '3E1593'
Icon-File      'native-ledger-file'    260  723 '3E1593'
Icon-Wallet    'native-ledger-wallet'  430  724 '3E1593'
Icon-Checklist 'native-ledger-check'   570  723 '3E1593'
Icon-Bank      'native-ledger-bank'    720  724 '3E1593'

Icon-Database  'native-store-db'       1010 655 '0B49B5' 48 48
Icon-Lock      'native-store-lock'     1020 723 '0B49B5'
Icon-Database  'native-store-cipher'   1248 721 '0B49B5' 38 42
Icon-Scales    'native-verifier'       725  518 '3E1593'

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

Write-Host "Replaced icon layer with native draw.io geometry in $diagramPath"
