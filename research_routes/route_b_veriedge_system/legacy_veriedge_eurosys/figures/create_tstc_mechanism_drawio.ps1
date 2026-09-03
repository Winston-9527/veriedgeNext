$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outFile = Join-Path $scriptDir "fig_tstc_mechanism.drawio"

$cells = New-Object System.Collections.Generic.List[string]
$nextId = 2

function Escape-Xml([string]$text) {
    if ($null -eq $text) { return "" }
    return [System.Security.SecurityElement]::Escape($text)
}

function New-Id([string]$prefix) {
    $script:nextId += 1
    return "$prefix-$script:nextId"
}

function Add-Vertex([string]$id, [string]$value, [string]$style, [double]$x, [double]$y, [double]$w, [double]$h) {
    $escaped = Escape-Xml $value
    $cells.Add("        <mxCell id=""$id"" value=""$escaped"" style=""$style"" vertex=""1"" parent=""1""><mxGeometry x=""$x"" y=""$y"" width=""$w"" height=""$h"" as=""geometry""/></mxCell>")
}

function Add-Text([string]$id, [string]$value, [double]$x, [double]$y, [double]$w, [double]$h, [int]$fontSize, [string]$color, [int]$fontStyle, [string]$align) {
    $style = "text;html=1;strokeColor=none;fillColor=none;align=$align;verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=$fontSize;fontColor=$color;fontStyle=$fontStyle;"
    Add-Vertex $id $value $style $x $y $w $h
}

function Add-Box([string]$id, [double]$x, [double]$y, [double]$w, [double]$h, [string]$fill, [string]$stroke, [double]$strokeWidth, [double]$arc = 8) {
    $style = "rounded=1;whiteSpace=wrap;html=1;arcSize=$arc;fillColor=$fill;strokeColor=$stroke;strokeWidth=$strokeWidth;"
    Add-Vertex $id "" $style $x $y $w $h
}

function Add-Ellipse([string]$id, [string]$value, [double]$x, [double]$y, [double]$w, [double]$h, [string]$fill, [string]$stroke, [double]$strokeWidth, [int]$fontSize = 16, [string]$fontColor = "#1C2630") {
    $style = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=$fill;strokeColor=$stroke;strokeWidth=$strokeWidth;fontSize=$fontSize;fontColor=$fontColor;fontStyle=2;"
    Add-Vertex $id $value $style $x $y $w $h
}

function Add-Edge([string]$id, [double]$x1, [double]$y1, [double]$x2, [double]$y2, [string]$stroke, [double]$strokeWidth, [bool]$arrow = $true, [string]$dash = "0") {
    $endArrow = "block"
    $endFill = "1"
    if (-not $arrow) {
        $endArrow = "none"
        $endFill = "0"
    }
    $style = "endArrow=$endArrow;endFill=$endFill;html=1;rounded=0;strokeColor=$stroke;strokeWidth=$strokeWidth;dashed=$dash;"
    $cells.Add("        <mxCell id=""$id"" value="""" style=""$style"" edge=""1"" parent=""1""><mxGeometry relative=""1"" as=""geometry""><mxPoint x=""$x1"" y=""$y1"" as=""sourcePoint""/><mxPoint x=""$x2"" y=""$y2"" as=""targetPoint""/></mxGeometry></mxCell>")
}

function Add-Ortho([string]$id, [double]$x1, [double]$y1, [double]$x2, [double]$y2, [string]$stroke, [double]$strokeWidth, [bool]$arrow = $true) {
    $endArrow = "block"
    $endFill = "1"
    if (-not $arrow) {
        $endArrow = "none"
        $endFill = "0"
    }
    $style = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=$endArrow;endFill=$endFill;strokeColor=$stroke;strokeWidth=$strokeWidth;"
    $cells.Add("        <mxCell id=""$id"" value="""" style=""$style"" edge=""1"" parent=""1""><mxGeometry relative=""1"" as=""geometry""><mxPoint x=""$x1"" y=""$y1"" as=""sourcePoint""/><mxPoint x=""$x2"" y=""$y2"" as=""targetPoint""/></mxGeometry></mxCell>")
}

function Add-ServerIcon([double]$cx, [double]$cy) {
    for ($i = 0; $i -lt 3; $i++) {
        $y = $cy - 20 + $i * 18
        Add-Box (New-Id "server-bar") ($cx - 24) $y 48 10 "#E1F3E8" "#2F8F4F" 2 15
        Add-Vertex (New-Id "server-dot") "" "ellipse;html=1;fillColor=#2F8F4F;strokeColor=#2F8F4F;" ($cx - 17) ($y + 3) 4 4
    }
}

function Add-DocumentIcon([double]$x, [double]$y) {
    Add-Vertex "icon-document" "" "shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;darkOpacity=0.05;fillColor=#FFFFFF;strokeColor=#1557A6;strokeWidth=2;" $x $y 34 48
    Add-Edge (New-Id "doc-line") ($x + 8) ($y + 18) ($x + 27) ($y + 18) "#1557A6" 1 $false
    Add-Edge (New-Id "doc-line") ($x + 8) ($y + 28) ($x + 27) ($y + 28) "#1557A6" 1 $false
    Add-Edge (New-Id "doc-line") ($x + 8) ($y + 38) ($x + 23) ($y + 38) "#1557A6" 1 $false
}

function Add-SearchIcon([double]$cx, [double]$cy) {
    Add-Ellipse (New-Id "search-lens") "" ($cx - 19) ($cy - 19) 38 38 "#FFFFFF" "#0E6F78" 3 10
    Add-Edge (New-Id "search-handle") ($cx + 13) ($cy + 13) ($cx + 34) ($cy + 34) "#0E6F78" 3 $false
}

function Add-DiceIcon([double]$cx, [double]$cy) {
    Add-Box (New-Id "dice") ($cx - 18) ($cy - 18) 36 36 "#FFFFFF" "#0E6F78" 2 12
    foreach ($p in @(@(-8,-8),@(8,-8),@(0,0),@(-8,8),@(8,8))) {
        Add-Vertex (New-Id "dice-dot") "" "ellipse;html=1;fillColor=#0E6F78;strokeColor=#0E6F78;" ($cx + $p[0] - 2) ($cy + $p[1] - 2) 4 4
    }
}

function Add-FilterIcon([double]$cx, [double]$cy) {
    Add-Vertex (New-Id "filter-top") "" "shape=trapezoid;perimeter=trapezoidPerimeter;whiteSpace=wrap;html=1;fixedSize=1;fillColor=#EAF7F7;strokeColor=#0E6F78;strokeWidth=2;" ($cx - 24) ($cy - 17) 48 18
    Add-Vertex (New-Id "filter-stem") "" "rounded=0;whiteSpace=wrap;html=1;fillColor=#EAF7F7;strokeColor=#0E6F78;strokeWidth=2;" ($cx - 8) ($cy + 1) 16 26
}

function Add-TargetIcon([double]$cx, [double]$cy) {
    Add-Ellipse (New-Id "target-o") "" ($cx - 35) ($cy - 35) 70 70 "#FFFFFF" "#0E6F78" 3
    Add-Ellipse (New-Id "target-m") "" ($cx - 23) ($cy - 23) 46 46 "none" "#0E6F78" 2
    Add-Ellipse (New-Id "target-c") "" ($cx - 8) ($cy - 8) 16 16 "#0E6F78" "#0E6F78" 2
}

# Panels
Add-Box "panel-top" 10 10 1580 190 "#F3F8FF" "#1557A6" 2 6
Add-Box "panel-thc" 10 245 1580 220 "#F7F7F7" "#9AA2AD" 2 6
Add-Box "panel-tstc" 10 505 1580 330 "#F1FBFC" "#0E6F78" 2 6

Add-Text "title-top" "Committed sharded prefill instance" 390 16 820 42 28 "#1C2630" 1 "center"
Add-Text "title-thc" "THC baseline" 650 260 300 42 28 "#1C2630" 1 "center"
Add-Text "title-tstc" "TSTC escalation path" 620 522 360 42 28 "#0E6F78" 1 "center"

# Top row
Add-DocumentIcon 60 75
Add-Text "tokens-label" "tokens" 43 130 70 24 15 "#1C2630" 0 "center"

$shards = @(
    @("s1",150,80,"Shard 1"),
    @("s2",490,80,"Shard 2"),
    @("s3",830,80,"Shard 3")
)
foreach ($s in $shards) {
    Add-Box $s[0] $s[1] $s[2] 180 86 "#FFFFFF" "#1557A6" 2 12
    Add-ServerIcon ($s[1] + 90) ($s[2] + 32)
    Add-Text "$($s[0])-label" $s[3] ($s[1] + 38) ($s[2] + 58) 104 24 20 "#1C2630" 1 "center"
}

Add-Ellipse "c1" "C<sub>1</sub>" 385 82 78 78 "#FFF0E5" "#F47B20" 3 24 "#F47B20"
Add-Ellipse "c2" "C<sub>2</sub>" 725 82 78 78 "#FFF0E5" "#F47B20" 3 24 "#F47B20"
Add-Ellipse "c3" "C<sub>3</sub>" 1065 82 78 78 "#FFF0E5" "#F47B20" 3 24 "#F47B20"

Add-Text "boundary-label" "checked boundaries<br><i>&#8492;</i><sub>j</sub> = {C<sub>1</sub>, C<sub>2</sub>, C<sub>3</sub>}" 1220 78 260 64 18 "#1557A6" 0 "left"

Add-Edge "e-token-s1" 110 123 150 123 "#1C2630" 2 $true
Add-Edge "e-s1-c1" 330 123 385 123 "#1C2630" 2 $true
Add-Edge "e-c1-s2" 463 123 490 123 "#1C2630" 2 $true
Add-Edge "e-s2-c2" 670 123 725 123 "#1C2630" 2 $true
Add-Edge "e-c2-s3" 803 123 830 123 "#1C2630" 2 $true
Add-Edge "e-s3-c3" 1010 123 1065 123 "#1C2630" 2 $true

# THC row
Add-Box "th1" 120 340 230 70 "#FFFFFF" "#6F7782" 2 8
Add-Box "th2" 460 340 230 70 "#FFFFFF" "#6F7782" 2 8
Add-Box "th3" 800 340 230 70 "#FFFFFF" "#6F7782" 2 8
Add-Box "thout" 1080 340 230 70 "#FFFFFF" "#0E6F78" 2 8
Add-Text "th1-t" "Hash(Ser(<i>H</i><sub>j,1</sub>))" 132 359 206 32 17 "#1C2630" 0 "center"
Add-Text "th2-t" "Hash(Ser(<i>H</i><sub>j,2</sub>))" 472 359 206 32 17 "#1C2630" 0 "center"
Add-Text "th3-t" "Hash(Ser(<i>H</i><sub>j,3</sub>))" 812 359 206 32 17 "#1C2630" 0 "center"
Add-SearchIcon 1125 375
Add-Text "thout-t" "first mismatch" 1160 358 120 34 16 "#1C2630" 0 "left"
Add-Text "full-tensor" "full tensor" 145 420 180 24 16 "#6F7782" 0 "center"
Add-Text "exact-compare" "exact compare" 485 420 180 24 16 "#6F7782" 0 "center"
Add-Text "byte-chain" "byte-level chain" 815 420 200 24 16 "#6F7782" 0 "center"
Add-Text "byte-note" "byte difference &#8658; mismatch" 1010 300 270 26 16 "#C9252C" 0 "center"
Add-Text "strict-note" "strict byte equality<br>sensitive to honest drift" 1315 360 180 56 15 "#6F7782" 2 "center"

Add-Ortho "v-c1-th1" 424 160 235 340 "#6F7782" 2 $true
Add-Ortho "v-c2-th2" 764 160 575 340 "#6F7782" 2 $true
Add-Ortho "v-c3-th3" 1104 160 915 340 "#6F7782" 2 $true
Add-Edge "e-th1-th2" 350 375 460 375 "#1C2630" 2 $true
Add-Edge "e-th2-th3" 690 375 800 375 "#1C2630" 2 $true
Add-Edge "e-th3-out" 1030 375 1080 375 "#1C2630" 2 $true

# TSTC row
Add-Box "sample" 45 615 195 70 "#FFFFFF" "#0E6F78" 2 8
Add-Box "sketch" 285 615 245 70 "#FFFFFF" "#0E6F78" 2 8
Add-Box "compare" 565 610 265 82 "#FFFFFF" "#0E6F78" 2 8
Add-Box "digest" 860 615 230 70 "#FFFFFF" "#0E6F78" 2 8
Add-Box "loc" 1120 615 240 70 "#FFFFFF" "#0E6F78" 2 8
Add-DiceIcon 95 650
Add-Text "sample-t" "sample&nbsp; &#937;<sub>k</sub>" 118 632 105 36 16 "#1C2630" 0 "left"
Add-FilterIcon 335 650
Add-Text "sketch-t" "sketch<br><i>z</i><sub>j,k</sub> = &#934;<sub>j,k</sub>(<i>H</i><sub>j,k</sub>)" 365 625 150 50 16 "#1C2630" 0 "left"
Add-Text "compare-t" "compare gap<br>&#948;<sub>j,k</sub> = &#956;(<i>z</i><sub>j,k</sub>, <i>z</i>&prime;<sub>j,k</sub>)<br>&#948;<sub>j,k</sub> &#8804; &#915;<sub>j,k</sub>" 580 616 235 68 15 "#1C2630" 0 "center"
Add-Text "digest-t" "digest&nbsp; <i>g</i><sub>j,k</sub><br>chain&nbsp; <i>c</i><sub>j,k</sub>" 880 630 190 42 16 "#1C2630" 0 "center"
Add-Text "loc-t" "first &#948;<sub>j,k</sub> &gt; &#915;<sub>j,k</sub><br>&#8594; <i>b</i><sup>*</sup><sub>j</sub>" 1135 627 210 46 16 "#1C2630" 0 "center"

Add-Edge "e-sample-sketch" 240 650 285 650 "#1557A6" 2 $true
Add-Edge "e-sketch-compare" 530 650 565 650 "#1557A6" 2 $true
Add-Edge "e-compare-digest" 830 650 860 650 "#1557A6" 2 $true
Add-Edge "e-digest-loc" 1090 650 1120 650 "#1557A6" 2 $true

Add-Edge "bus-c1" 424 160 424 520 "#0E6F78" 1.5 $false
Add-Edge "bus-c2" 764 160 764 520 "#0E6F78" 1.5 $false
Add-Edge "bus-c3" 1104 160 1104 520 "#0E6F78" 1.5 $false
Add-Edge "bus-h" 424 520 1104 520 "#0E6F78" 1.5 $false
Add-Ortho "bus-sample" 424 520 142 615 "#0E6F78" 2 $true

Add-Text "for-each" "for each <i>k</i> &#8712; <i>&#8492;</i><sub>j</sub>" 145 565 190 28 16 "#0E6F78" 0 "center"
Add-Text "ref-sketch" "reference or replayed sketch&nbsp; <i>z</i>&prime;<sub>j,k</sub>" 500 565 360 28 16 "#0E6F78" 0 "center"
Add-Text "reveal-note" "reveal sketches, not full checkpoints" 140 760 360 28 16 "#0E6F78" 0 "center"
Add-Text "boundary-note" "above-tolerance boundary &#8594; <i>b</i><sup>*</sup><sub>j</sub> via &#963;<sub>j</sub>" 670 760 430 28 16 "#0E6F78" 0 "center"
Add-Text "benefit-note" "compact sketches<br>calibrated tolerance<br>digest chain preserves localization" 1280 700 230 72 16 "#0E6F78" 2 "center"
Add-TargetIcon 1515 728

$cellXml = [string]::Join("`n", $cells)
$modified = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fffzzz")
$xml = @"
<mxfile host="app.diagrams.net" modified="$modified" agent="Codex" version="24.7.17" type="device">
  <diagram id="tstc-mechanism" name="TSTC mechanism">
    <mxGraphModel dx="1500" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1600" pageHeight="850" math="1" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
$cellXml
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
"@

$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($outFile, $xml, $utf8)
Write-Host "Wrote $outFile"
