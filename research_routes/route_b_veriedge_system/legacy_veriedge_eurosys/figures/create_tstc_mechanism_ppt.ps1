param(
    [switch]$PlainMath
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectDir = Split-Path -Parent $scriptDir
$template = Join-Path $scriptDir "fig_system_model_workflow_v2.pptx"
$output = Join-Path $scriptDir "fig_tstc_mechanism_ppt.pptx"
$tmpRoot = Join-Path $projectDir "tmp"
$tmpDir = Join-Path $tmpRoot ("pptx_tstc_mechanism_" + [System.Guid]::NewGuid().ToString("N"))

function Resolve-UnderProject([string]$path) {
    $resolvedProject = [System.IO.Path]::GetFullPath($projectDir)
    $resolvedPath = [System.IO.Path]::GetFullPath($path)
    if (-not $resolvedPath.StartsWith($resolvedProject, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to modify a path outside the project: $resolvedPath"
    }
    return $resolvedPath
}

$tmpDir = Resolve-UnderProject $tmpDir
$output = Resolve-UnderProject $output

if (-not (Test-Path $template)) {
    throw "Template PPTX not found: $template"
}

New-Item -ItemType Directory -Path $tmpDir | Out-Null

[System.IO.Compression.ZipFile]::ExtractToDirectory($template, $tmpDir)

$script:shapeId = 1
$script:shapeTree = New-Object System.Text.StringBuilder
$emuPerInch = 914400.0
$slideW = 12344400.0 / $emuPerInch
$slideH = 7497763.0 / $emuPerInch
$tikzW = 16.0
$tikzH = 8.62
$sx = $slideW / $tikzW
$sy = $slideH / $tikzH

function XmlEscape([string]$text) {
    if ($null -eq $text) { return "" }
    return [System.Security.SecurityElement]::Escape($text)
}

function Emu([double]$inch) {
    return [int64][Math]::Round($inch * 914400.0)
}

function LnW([double]$pt) {
    return [int64][Math]::Round($pt * 12700.0)
}

function X([double]$x) { return $x * $sx }
function Y([double]$y) { return ($tikzH - $y) * $sy }

function NextId() {
    $script:shapeId += 1
    return $script:shapeId
}

function AddRaw([string]$xml) {
    [void]$script:shapeTree.AppendLine($xml)
}

function FillXml([string]$hex) {
    if ([string]::IsNullOrWhiteSpace($hex) -or $hex -eq "none") {
        return "<a:noFill/>"
    }
    return "<a:solidFill><a:srgbClr val=""$hex""/></a:solidFill>"
}

function LineXml([string]$hex, [double]$pt, [string]$dash, [bool]$arrow) {
    if ([string]::IsNullOrWhiteSpace($hex) -or $hex -eq "none" -or $pt -le 0) {
        return "<a:ln><a:noFill/></a:ln>"
    }
    $dashXml = ""
    if ($dash -ne "") {
        $dashXml = "<a:prstDash val=""$dash""/>"
    }
    $headXml = ""
    if ($arrow) {
        $headXml = "<a:headEnd type=""triangle"" w=""sm"" len=""sm""/>"
    }
    return "<a:ln w=""$(LnW $pt)""><a:solidFill><a:srgbClr val=""$hex""/></a:solidFill>$dashXml$headXml</a:ln>"
}

function TextParagraph([string]$text, [int]$pt, [string]$color, [bool]$bold, [bool]$italic, [string]$align) {
    $b = ""
    if ($bold) { $b = " b=""1""" }
    $i = ""
    if ($italic) { $i = " i=""1""" }
    $esc = XmlEscape $text
    return "<a:p><a:pPr algn=""$align""/><a:r><a:rPr lang=""en-US"" sz=""$($pt * 100)""$b$i><a:solidFill><a:srgbClr val=""$color""/></a:solidFill><a:latin typeface=""Aptos""/><a:ea typeface=""Aptos""/><a:cs typeface=""Cambria Math""/></a:rPr><a:t>$esc</a:t></a:r><a:endParaRPr lang=""en-US"" sz=""$($pt * 100)""/></a:p>"
}

function TextBody([string[]]$lines, [int]$pt, [string]$color, [bool]$bold, [bool]$italic, [string]$align, [string]$anchor) {
    if ($anchor -eq "mid") { $anchor = "ctr" }
    $paras = New-Object System.Text.StringBuilder
    foreach ($line in $lines) {
        [void]$paras.Append((TextParagraph $line $pt $color $bold $italic $align))
    }
    return "<p:txBody><a:bodyPr wrap=""square"" anchor=""$anchor"" lIns=""45720"" tIns=""45720"" rIns=""45720"" bIns=""45720""/><a:lstStyle/>$($paras.ToString())</p:txBody>"
}

function MathBody([string]$math, [int]$pt, [string]$color, [string]$align, [string]$anchor) {
    if ($anchor -eq "mid") { $anchor = "ctr" }
    if ($PlainMath) {
        return TextBody @($math) $pt $color $false $false $align $anchor
    }
    $esc = XmlEscape $math
    $jc = "centerGroup"
    if ($align -eq "l") { $jc = "left" }
    if ($align -eq "r") { $jc = "right" }
    return "<p:txBody><a:bodyPr wrap=""square"" lIns=""27432"" tIns=""27432"" rIns=""27432"" bIns=""27432"" rtlCol=""0"" anchor=""$anchor""><a:noAutofit/></a:bodyPr><a:lstStyle/><a:p><a:pPr algn=""$align""/><a14:m><m:oMathPara xmlns:m=""http://schemas.openxmlformats.org/officeDocument/2006/math""><m:oMathParaPr><m:jc m:val=""$jc""/></m:oMathParaPr><m:oMath xmlns:m=""http://schemas.openxmlformats.org/officeDocument/2006/math""><m:r><a:rPr lang=""en-US"" sz=""$($pt * 100)"" b=""0"" i=""1"" dirty=""0"" smtClean=""0""><a:solidFill><a:srgbClr val=""$color""/></a:solidFill><a:latin typeface=""Cambria Math"" panose=""02040503050406030204"" pitchFamily=""18"" charset=""0""/><a:ea typeface=""Cambria Math"" panose=""02040503050406030204"" pitchFamily=""18"" charset=""0""/><a:cs typeface=""Cambria Math"" pitchFamily=""18"" charset=""0""/></a:rPr><m:t>$esc</m:t></m:r></m:oMath></m:oMathPara></a14:m><a:endParaRPr dirty=""0""/></a:p></p:txBody>"
}

function AddShape([double]$x, [double]$y, [double]$w, [double]$h, [string]$preset, [string]$fill, [string]$line, [double]$linePt, [string]$txBody, [string]$name) {
    $id = NextId
    if ([string]::IsNullOrWhiteSpace($preset)) { $preset = "rect" }
    $safeName = XmlEscape $name
    $offX = Emu $x
    $offY = Emu $y
    $extW = Emu $w
    $extH = Emu $h
    $fillPart = FillXml $fill
    $linePart = LineXml $line $linePt "" $false
    $xml = "<p:sp><p:nvSpPr><p:cNvPr id=""$id"" name=""$safeName""/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x=""$offX"" y=""$offY""/><a:ext cx=""$extW"" cy=""$extH""/></a:xfrm><a:prstGeom prst=""$preset""><a:avLst/></a:prstGeom>$fillPart$linePart</p:spPr>$txBody</p:sp>"
    AddRaw $xml
}

function AddText([double]$x, [double]$y, [double]$w, [double]$h, [string[]]$lines, [int]$pt, [string]$color, [bool]$bold, [bool]$italic, [string]$align, [string]$anchor, [string]$name) {
    AddShape $x $y $w $h "rect" "none" "none" 0 (TextBody $lines $pt $color $bold $italic $align $anchor) $name
}

function AddMath([double]$x, [double]$y, [double]$w, [double]$h, [string]$math, [int]$pt, [string]$color, [string]$align, [string]$anchor, [string]$name) {
    if ($PlainMath) {
        AddShape $x $y $w $h "rect" "none" "none" 0 (TextBody @($math) $pt $color $false $false $align $anchor) $name
        return
    }

    $id = NextId
    $safeName = XmlEscape $name
    $offX = Emu $x
    $offY = Emu $y
    $extW = Emu $w
    $extH = Emu $h
    $choiceBody = MathBody $math $pt $color $align $anchor
    $fallbackBody = TextBody @($math) $pt $color $false $false $align $anchor
    $spPr = "<p:spPr><a:xfrm><a:off x=""$offX"" y=""$offY""/><a:ext cx=""$extW"" cy=""$extH""/></a:xfrm><a:prstGeom prst=""rect""><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>"
    $choice = "<p:sp><p:nvSpPr><p:cNvPr id=""$id"" name=""$safeName""/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>$spPr$choiceBody</p:sp>"
    $fallback = "<p:sp><p:nvSpPr><p:cNvPr id=""$id"" name=""$safeName fallback""/><p:cNvSpPr txBox=""1""/><p:nvPr/></p:nvSpPr>$spPr$fallbackBody</p:sp>"
    AddRaw "<mc:AlternateContent><mc:Choice Requires=""a14"">$choice</mc:Choice><mc:Fallback>$fallback</mc:Fallback></mc:AlternateContent>"
}

function AddPanel([double]$x1, [double]$y1, [double]$x2, [double]$y2, [string]$fill, [string]$line, [string]$name) {
    AddShape (X $x1) (Y $y2) (($x2 - $x1) * $sx) (($y2 - $y1) * $sy) "roundRect" $fill $line 0.8 "" $name
}

function AddNode([double]$cx, [double]$cy, [double]$wcm, [double]$hcm, [string]$preset, [string]$fill, [string]$line, [double]$linePt, [string]$txBody, [string]$name) {
    $w = $wcm * $sx
    $h = $hcm * $sy
    AddShape ((X $cx) - $w / 2.0) ((Y $cy) - $h / 2.0) $w $h $preset $fill $line $linePt $txBody $name
}

function AddNodeText([double]$cx, [double]$cy, [double]$wcm, [double]$hcm, [string[]]$lines, [int]$pt, [string]$color, [bool]$bold, [bool]$italic, [string]$align, [string]$anchor, [string]$name) {
    $w = $wcm * $sx
    $h = $hcm * $sy
    AddText ((X $cx) - $w / 2.0) ((Y $cy) - $h / 2.0) $w $h $lines $pt $color $bold $italic $align $anchor $name
}

function AddNodeMath([double]$cx, [double]$cy, [double]$wcm, [double]$hcm, [string]$math, [int]$pt, [string]$color, [string]$align, [string]$anchor, [string]$name) {
    $w = $wcm * $sx
    $h = $hcm * $sy
    AddMath ((X $cx) - $w / 2.0) ((Y $cy) - $h / 2.0) $w $h $math $pt $color $align $anchor $name
}

function AddLine([double]$x1, [double]$y1, [double]$x2, [double]$y2, [string]$color, [double]$pt, [bool]$arrow, [string]$dash, [string]$name) {
    $sx1 = X $x1
    $sy1 = Y $y1
    $sx2 = X $x2
    $sy2 = Y $y2
    $offX = [Math]::Min($sx1, $sx2)
    $offY = [Math]::Min($sy1, $sy2)
    $cx = [Math]::Abs($sx2 - $sx1)
    $cy = [Math]::Abs($sy2 - $sy1)
    if ($cx -lt 0.0001) { $cx = 0.0001 }
    if ($cy -lt 0.0001) { $cy = 0.0001 }
    $flipH = ""
    if ($sx2 -lt $sx1) { $flipH = " flipH=""1""" }
    $flipV = ""
    if ($sy2 -lt $sy1) { $flipV = " flipV=""1""" }
    $id = NextId
    $safeName = XmlEscape $name
    $offXEmu = Emu $offX
    $offYEmu = Emu $offY
    $cxEmu = Emu $cx
    $cyEmu = Emu $cy
    $linePart = LineXml $color $pt $dash $arrow
    $xml = "<p:cxnSp><p:nvCxnSpPr><p:cNvPr id=""$id"" name=""$safeName""/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr><p:spPr><a:xfrm$flipH$flipV><a:off x=""$offXEmu"" y=""$offYEmu""/><a:ext cx=""$cxEmu"" cy=""$cyEmu""/></a:xfrm><a:prstGeom prst=""line""><a:avLst/></a:prstGeom>$linePart</p:spPr></p:cxnSp>"
    AddRaw $xml
}

function AddElbow([double]$x1, [double]$y1, [double]$xm, [double]$ym, [double]$x2, [double]$y2, [string]$color, [double]$pt, [string]$name) {
    AddLine $x1 $y1 $xm $ym $color $pt $false "" "$name segment 1"
    AddLine $xm $ym $x2 $ym $color $pt $false "" "$name segment 2"
    AddLine $x2 $ym $x2 $y2 $color $pt $true "" "$name segment 3"
}

function AddMiniRect([double]$cx, [double]$cy, [double]$wcm, [double]$hcm, [string]$fill, [string]$line, [string]$name) {
    AddNode $cx $cy $wcm $hcm "roundRect" $fill $line 0.55 "" $name
}

function AddDocumentIcon([double]$cx, [double]$cy) {
    AddNode ($cx - 0.03) ($cy + 0.04) 0.38 0.50 "rect" "FFFFFF" "6F7782" 0.65 "" "token document"
    AddLine ($cx - 0.16) ($cy + 0.09) ($cx + 0.12) ($cy + 0.09) "6F7782" 0.5 $false "" "document line 1"
    AddLine ($cx - 0.16) ($cy - 0.02) ($cx + 0.12) ($cy - 0.02) "6F7782" 0.5 $false "" "document line 2"
    AddLine ($cx - 0.16) ($cy - 0.13) ($cx + 0.06) ($cy - 0.13) "6F7782" 0.5 $false "" "document line 3"
}

function AddServerIcon([double]$cx, [double]$cy) {
    AddMiniRect $cx ($cy + 0.12) 0.42 0.12 "E1F3E8" "58A56E" "server bar top"
    AddMiniRect $cx $cy 0.42 0.12 "E1F3E8" "58A56E" "server bar middle"
    AddMiniRect $cx ($cy - 0.12) 0.42 0.12 "E1F3E8" "58A56E" "server bar bottom"
}

function AddSearchIcon([double]$cx, [double]$cy) {
    AddNode $cx $cy 0.33 0.33 "ellipse" "none" "0E6F78" 1.0 "" "search lens"
    AddLine ($cx + 0.13) ($cy - 0.13) ($cx + 0.28) ($cy - 0.28) "0E6F78" 1.0 $false "" "search handle"
}

function AddDiceIcon([double]$cx, [double]$cy) {
    AddNode $cx $cy 0.38 0.38 "roundRect" "FFFFFF" "0E6F78" 0.8 "" "sample dice body"
    foreach ($d in @(@(-0.10,0.10),@(0.10,0.10),@(0,0),@(-0.10,-0.10),@(0.10,-0.10))) {
        AddNode ($cx + $d[0]) ($cy + $d[1]) 0.035 0.035 "ellipse" "0E6F78" "0E6F78" 0.1 "" "sample dice dot"
    }
}

function AddFilterIcon([double]$cx, [double]$cy) {
    AddNode $cx ($cy + 0.08) 0.42 0.16 "trapezoid" "EAF7F7" "0E6F78" 0.7 "" "filter funnel top"
    AddNode $cx ($cy - 0.11) 0.16 0.22 "rect" "EAF7F7" "0E6F78" 0.7 "" "filter stem"
}

function AddTargetIcon([double]$cx, [double]$cy) {
    AddNode $cx $cy 0.62 0.62 "ellipse" "FFFFFF" "0E6F78" 0.9 "" "target outer"
    AddNode $cx $cy 0.40 0.40 "ellipse" "none" "0E6F78" 0.8 "" "target middle"
    AddNode $cx $cy 0.14 0.14 "ellipse" "0E6F78" "0E6F78" 0.8 "" "target core"
}

$Ink = "1C2630"
$MutedGray = "6F7782"
$RoutineBlue = "1557A6"
$Teal = "0E6F78"
$Orange = "F47B20"
$AlertRed = "C9252C"
$PanelBlue = "F3F8FF"
$PanelGray = "F7F7F7"
$PanelTeal = "F1FBFC"
$SoftOrange = "FFF0E5"

$Omega = [string][char]0x03A9
$Phi = [string][char]0x03A6
$delta = [string][char]0x03B4
$Gamma = [string][char]0x0393
$mu = [string][char]0x03BC
$sigma = [string][char]0x03C3
$Bcal = [string][char]0x212C
$prime = [string][char]0x2032
$le = [string][char]0x2264
$sub1 = [string][char]0x2081
$sub2 = [string][char]0x2082
$sub3 = [string][char]0x2083
$subj = [string][char]0x2C7C
$subk = [string][char]0x2096

AddPanel 0.25 6.35 15.75 8.30 $PanelBlue $RoutineBlue "top committed panel"
AddPanel 0.25 3.82 15.75 5.95 $PanelGray "B8BEC6" "thc baseline panel"
AddPanel 0.25 0.32 15.75 3.46 $PanelTeal $Teal "tstc escalation panel"

AddNodeText 8.00 8.00 7.0 0.36 @("Committed sharded prefill instance") 17 $Ink $true $false "ctr" "mid" "top title"
AddNodeText 8.00 5.62 3.4 0.36 @("THC baseline") 17 $Ink $true $false "ctr" "mid" "middle title"
AddNodeText 8.00 3.13 4.3 0.36 @("TSTC escalation path") 17 $Teal $true $false "ctr" "mid" "bottom title"

AddNodeText 0.90 6.96 0.85 0.23 @("tokens") 9 $Ink $false $false "ctr" "mid" "tokens label"
AddDocumentIcon 0.90 7.43

foreach ($shard in @(@(2.45,7.13,"Shard 1"),@(5.75,7.13,"Shard 2"),@(9.05,7.13,"Shard 3"))) {
    AddNode $shard[0] $shard[1] 1.72 0.86 "roundRect" "FFFFFF" $RoutineBlue 0.8 "" "$($shard[2]) box"
    AddServerIcon $shard[0] ($shard[1] + 0.17)
    AddNodeText $shard[0] ($shard[1] - 0.18) 1.20 0.22 @($shard[2]) 10 $Ink $true $false "ctr" "mid" "$($shard[2]) label"
}

foreach ($ckpt in @(@(4.05,7.13,"C$sub1"),@(7.35,7.13,"C$sub2"),@(10.65,7.13,"C$sub3"))) {
    AddNode $ckpt[0] $ckpt[1] 0.72 0.72 "ellipse" $SoftOrange $Orange 0.9 "" "$($ckpt[2]) checkpoint"
    AddNodeMath $ckpt[0] $ckpt[1] 0.66 0.38 $ckpt[2] 13 $Orange "ctr" "mid" "$($ckpt[2]) equation"
}

AddLine 1.22 7.13 1.59 7.13 $Ink 0.85 $true "" "tokens to shard1"
AddLine 3.31 7.13 3.69 7.13 $Ink 0.85 $true "" "shard1 to C1"
AddLine 4.41 7.13 4.89 7.13 $Ink 0.85 $true "" "C1 to shard2"
AddLine 6.61 7.13 6.99 7.13 $Ink 0.85 $true "" "shard2 to C2"
AddLine 7.71 7.13 8.19 7.13 $Ink 0.85 $true "" "C2 to shard3"
AddLine 9.91 7.13 10.29 7.13 $Ink 0.85 $true "" "shard3 to C3"

AddNodeText 13.25 7.42 2.35 0.28 @("checked boundaries") 9 $RoutineBlue $false $false "l" "mid" "checked boundaries label"
AddNodeMath 13.25 7.13 2.35 0.32 "$Bcal$subj = {C$sub1, C$sub2, C$sub3}" 12 $RoutineBlue "l" "mid" "boundary equation"

foreach ($th in @(
    @(2.45,4.70,"Hash(Ser(H$subj,$sub1))"),
    @(5.75,4.70,"Hash(Ser(H$subj,$sub2))"),
    @(9.05,4.70,"Hash(Ser(H$subj,$sub3))")
)) {
    AddNode $th[0] $th[1] 2.20 0.74 "roundRect" "FFFFFF" $MutedGray 0.65 "" "$($th[2]) box"
    AddNodeMath $th[0] $th[1] 2.06 0.40 $th[2] 10 $Ink "ctr" "mid" "$($th[2]) equation"
}

AddNode 11.70 4.70 2.20 0.74 "roundRect" "FFFFFF" $Teal 0.8 "" "first mismatch box"
AddSearchIcon 11.00 4.70
AddNodeText 11.85 4.70 1.42 0.30 @("first mismatch") 9 $Ink $false $false "ctr" "mid" "first mismatch label"

AddElbow 4.05 6.77 4.05 6.43 2.45 5.07  $MutedGray 0.75 "C1 to THC1"
AddElbow 7.35 6.77 7.35 6.43 5.75 5.07  $MutedGray 0.75 "C2 to THC2"
AddElbow 10.65 6.77 10.65 6.43 9.05 5.07  $MutedGray 0.75 "C3 to THC3"
AddLine 3.55 4.70 4.65 4.70 $Ink 0.85 $true "" "THC1 to THC2"
AddLine 6.85 4.70 7.95 4.70 $Ink 0.85 $true "" "THC2 to THC3"
AddLine 10.15 4.70 10.60 4.70 $Ink 0.85 $true "" "THC3 to outcome"

AddNodeText 2.45 4.05 1.35 0.22 @("full tensor") 8 $MutedGray $false $false "ctr" "mid" "full tensor note"
AddNodeText 5.75 4.05 1.35 0.22 @("exact compare") 8 $MutedGray $false $false "ctr" "mid" "exact compare note"
AddNodeText 9.05 4.05 1.50 0.22 @("byte-level chain") 8 $MutedGray $false $false "ctr" "mid" "byte-level chain note"
AddNodeText 11.45 5.25 2.20 0.28 @("byte difference => mismatch") 9 $AlertRed $false $false "ctr" "mid" "byte difference note"
AddNodeText 13.80 4.78 2.55 0.45 @("strict byte equality","sensitive to honest drift") 8 $MutedGray $false $true "ctr" "mid" "THC limitation note"

AddNode 1.55 2.02 1.90 0.72 "roundRect" "FFFFFF" $Teal 0.7 "" "sample box"
AddDiceIcon 0.88 2.02
AddNodeText 1.72 2.02 1.20 0.26 @("sample") 8 $Ink $false $false "ctr" "mid" "sample label"
AddNodeMath 2.11 2.02 0.50 0.26 "$Omega$subk" 10 $Ink "ctr" "mid" "sample omega"

AddNode 4.10 2.02 2.35 0.72 "roundRect" "FFFFFF" $Teal 0.7 "" "sketch box"
AddFilterIcon 3.22 2.05
AddNodeText 4.15 2.20 1.35 0.22 @("sketch") 8 $Ink $false $false "ctr" "mid" "sketch label"
AddNodeMath 4.35 1.90 1.75 0.30 "z$subj,$subk = $Phi$subj,$subk(H$subj,$subk)" 9 $Ink "ctr" "mid" "sketch equation"

AddNode 6.85 2.02 2.18 0.88 "roundRect" "FFFFFF" $Teal 0.7 "" "compare box"
AddNodeText 6.85 2.25 1.60 0.20 @("compare gap") 8 $Ink $false $false "ctr" "mid" "compare gap label"
AddNodeMath 6.85 2.02 1.95 0.26 "$delta$subj,$subk = $mu(z$subj,$subk,z$prime$subj,$subk)" 8 $Ink "ctr" "mid" "gap equation"
AddNodeMath 6.85 1.78 1.95 0.24 "$delta$subj,$subk $le $Gamma$subj,$subk" 8 $Ink "ctr" "mid" "threshold equation"

AddNode 9.55 2.02 2.22 0.72 "roundRect" "FFFFFF" $Teal 0.7 "" "digest box"
AddNodeMath 9.55 2.17 1.70 0.24 "digest g$subj,$subk" 8 $Ink "ctr" "mid" "digest equation"
AddNodeMath 9.55 1.88 1.70 0.24 "chain c$subj,$subk" 8 $Ink "ctr" "mid" "chain equation"

AddNode 12.05 2.02 2.15 0.74 "roundRect" "FFFFFF" $Teal 0.8 "" "localized boundary box"
AddNodeMath 12.05 2.14 1.90 0.26 "first $delta$subj,$subk > $Gamma$subj,$subk" 8 $Ink "ctr" "mid" "first above threshold equation"
AddNodeMath 12.05 1.86 1.70 0.24 "-> b*$subj" 9 $Ink "ctr" "mid" "localized boundary equation"

AddLine 2.50 2.02 2.92 2.02 $RoutineBlue 0.85 $true "" "sample to sketch"
AddLine 5.27 2.02 5.76 2.02 $RoutineBlue 0.85 $true "" "sketch to compare"
AddLine 7.94 2.02 8.44 2.02 $RoutineBlue 0.85 $true "" "compare to digest"
AddLine 10.66 2.02 10.98 2.02 $RoutineBlue 0.85 $true "" "digest to loc"

foreach ($xv in @(4.05,7.35,10.65)) {
    AddLine $xv 6.77 $xv 3.65 $Teal 0.62 $false "" "checkpoint to sketch bus"
}
AddLine 4.05 3.65 10.65 3.65 $Teal 0.62 $false "" "sketch bus"
AddLine 4.05 3.65 1.55 3.65 $Teal 0.62 $false "" "bus back to sample"
AddLine 1.55 3.65 1.55 2.38 $Teal 0.75 $true "" "sample input arrow"

AddNodeMath 2.55 2.70 1.85 0.28 "for each k in $Bcal$subj" 9 $Teal "ctr" "mid" "for each boundary equation"
AddNodeMath 6.85 2.72 2.55 0.28 "reference or replayed sketch z$prime$subj,$subk" 9 $Teal "ctr" "mid" "reference sketch equation"
AddNodeText 3.65 0.82 3.35 0.34 @("reveal sketches, not full checkpoints") 8 $Teal $false $false "ctr" "mid" "reveal sketches note"
AddNodeMath 9.30 0.82 3.95 0.34 "above-tolerance boundary -> b*$subj via $sigma$subj" 8 $Teal "ctr" "mid" "signature localization equation"
AddNodeText 13.70 1.42 2.45 0.60 @("compact sketches","calibrated tolerance","digest chain preserves localization") 8 $Teal $false $true "ctr" "mid" "tstc benefit note"
AddTargetIcon 15.00 1.42

$slideXml = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" mc:Ignorable="a14">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
$($script:shapeTree.ToString())
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr>
    <a:masterClrMapping/>
  </p:clrMapOvr>
</p:sld>
"@

$relsXml = "<?xml version=""1.0"" encoding=""UTF-8"" standalone=""yes""?><Relationships xmlns=""http://schemas.openxmlformats.org/package/2006/relationships""><Relationship Id=""rId1"" Type=""http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"" Target=""../slideLayouts/slideLayout1.xml""/><Relationship Id=""rId2"" Type=""http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"" Target=""../notesSlides/notesSlide1.xml""/></Relationships>"
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText((Join-Path $tmpDir "ppt\slides\slide1.xml"), $slideXml, $utf8)
[System.IO.File]::WriteAllText((Join-Path $tmpDir "ppt\slides\_rels\slide1.xml.rels"), $relsXml, $utf8)

if (Test-Path $output) {
    Remove-Item -LiteralPath $output -Force
}

$outStream = [System.IO.File]::Open($output, [System.IO.FileMode]::CreateNew)
try {
    $zipArchive = New-Object System.IO.Compression.ZipArchive($outStream, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $files = Get-ChildItem -LiteralPath $tmpDir -Recurse -File
        foreach ($file in $files) {
            $rel = $file.FullName.Substring($tmpDir.Length).TrimStart("\", "/")
            $entryName = $rel.Replace("\", "/")
            $entry = $zipArchive.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
            $entryStream = $entry.Open()
            try {
                $inStream = [System.IO.File]::OpenRead($file.FullName)
                try {
                    $inStream.CopyTo($entryStream)
                } finally {
                    $inStream.Dispose()
                }
            } finally {
                $entryStream.Dispose()
            }
        }
    } finally {
        $zipArchive.Dispose()
    }
} finally {
    $outStream.Dispose()
}

Write-Host "Wrote $output"
