$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$sourceImage = Join-Path $repoRoot 'fig_system_model_workflow_final.png'
$baseDrawio = Join-Path $repoRoot 'figures\fig_system_model_workflow_recreated_native_icons.drawio'
$outDrawio = Join-Path $repoRoot 'figures\fig_system_model_workflow_recreated_original_icons.drawio'
$iconDir = Join-Path $repoRoot 'figures\fig1_original_icons'

if (-not (Test-Path $iconDir)) {
  New-Item -ItemType Directory -Path $iconDir | Out-Null
}

$icons = @(
  @{ id='req-user';      crop=@(60, 15, 70, 74);      place=@(60, 28, 64, 64) },
  @{ id='req-file';      crop=@(70, 109, 46, 50);     place=@(74, 115, 48, 48) },
  @{ id='req-lock';      crop=@(72, 181, 44, 48);     place=@(74, 185, 48, 48) },
  @{ id='req-key';       crop=@(68, 250, 54, 52);     place=@(72, 255, 52, 52) },
  @{ id='req-shield';    crop=@(70, 320, 50, 50);     place=@(74, 318, 48, 52) },

  @{ id='orch-gear';     crop=@(530, 18, 70, 72);     place=@(518, 32, 62, 62) },
  @{ id='orch-search';   crop=@(552, 104, 42, 36);    place=@(540, 108, 44, 44) },
  @{ id='orch-users';    crop=@(550, 164, 44, 36);    place=@(540, 168, 44, 44) },
  @{ id='orch-grid';     crop=@(552, 224, 42, 36);    place=@(540, 228, 44, 44) },
  @{ id='orch-file';     crop=@(552, 284, 40, 36);    place=@(540, 288, 44, 44) },
  @{ id='orch-lock';     crop=@(536, 332, 34, 36);    place=@(535, 338, 30, 30) },

  @{ id='prov-pool';     crop=@(1036, 22, 58, 58);    place=@(1008, 34, 60, 60) },
  @{ id='p1-server';     crop=@(1065, 159, 45, 38);   place=@(1031, 165, 50, 42) },
  @{ id='p2-server';     crop=@(1212, 159, 45, 38);   place=@(1174, 165, 50, 42) },
  @{ id='p3-server';     crop=@(1358, 159, 45, 38);   place=@(1319, 165, 50, 42) },
  @{ id='p3-warning';    crop=@(1410, 176, 30, 28);   place=@(1360, 176, 40, 40) },
  @{ id='p4-server';     crop=@(1118, 326, 33, 29);   place=@(1062, 331, 36, 32) },
  @{ id='p5-server';     crop=@(1258, 326, 33, 29);   place=@(1202, 331, 36, 32) },

  @{ id='ledger-link';   crop=@(280, 666, 64, 52);    place=@(266, 648, 64, 64) },
  @{ id='ledger-file';   crop=@(268, 735, 40, 40);    place=@(258, 720, 42, 42) },
  @{ id='ledger-wallet'; crop=@(438, 738, 48, 35);    place=@(427, 720, 45, 42) },
  @{ id='ledger-check';  crop=@(572, 732, 40, 46);    place=@(568, 720, 42, 44) },
  @{ id='ledger-bank';   crop=@(724, 738, 39, 38);    place=@(716, 720, 44, 44) },

  @{ id='store-db';      crop=@(1052, 668, 52, 52);   place=@(1008, 650, 58, 58) },
  @{ id='store-lock';    crop=@(1064, 732, 44, 44);   place=@(1018, 718, 45, 45) },
  @{ id='store-cipher';  crop=@(1292, 731, 46, 48);   place=@(1244, 716, 46, 48) },
  @{ id='verifier';      crop=@(752, 528, 62, 62);    place=@(724, 516, 58, 58) }
)

function Convert-LightBackgroundToAlpha([System.Drawing.Bitmap] $bitmap) {
  for ($y = 0; $y -lt $bitmap.Height; $y++) {
    for ($x = 0; $x -lt $bitmap.Width; $x++) {
      $p = $bitmap.GetPixel($x, $y)
      $max = [Math]::Max($p.R, [Math]::Max($p.G, $p.B))
      $min = [Math]::Min($p.R, [Math]::Min($p.G, $p.B))

      # Remove the white and lightly tinted panel backgrounds while keeping
      # dark, colored, and gray icon strokes from the original figure.
      if ($min -ge 244 -and ($max - $min) -le 18) {
        $bitmap.SetPixel($x, $y, [System.Drawing.Color]::FromArgb(0, $p.R, $p.G, $p.B))
      } elseif ($min -ge 235 -and ($max - $min) -le 12) {
        $alpha = [Math]::Max(0, [Math]::Min(255, ($max - 235) * 18))
        $bitmap.SetPixel($x, $y, [System.Drawing.Color]::FromArgb($alpha, $p.R, $p.G, $p.B))
      }
    }
  }
}

function Save-Crop([System.Drawing.Image] $source, [hashtable] $icon) {
  $c = $icon.crop
  $rect = New-Object System.Drawing.Rectangle($c[0], $c[1], $c[2], $c[3])
  $bmp = New-Object System.Drawing.Bitmap($rect.Width, $rect.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $graphics = [System.Drawing.Graphics]::FromImage($bmp)
  try {
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.DrawImage($source, 0, 0, $rect, [System.Drawing.GraphicsUnit]::Pixel)
  } finally {
    $graphics.Dispose()
  }

  Convert-LightBackgroundToAlpha $bmp
  $path = Join-Path $iconDir ($icon.id + '.png')
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  return $path
}

function Add-ImageCell([System.Xml.XmlDocument] $doc, [System.Xml.XmlElement] $root, [string] $id, [string] $pngPath, [array] $place) {
  $bytes = [IO.File]::ReadAllBytes($pngPath)
  $b64 = [Convert]::ToBase64String($bytes)
  $cell = $doc.CreateElement('mxCell')
  $cell.SetAttribute('id', "origicon-$id")
  $cell.SetAttribute('parent', '1')
  # diagrams.net parses style fields on semicolons; use data:image/png,<base64>
  # rather than data:image/png;base64,<base64>.
  $cell.SetAttribute('style', "shape=image;html=1;imageAspect=1;aspect=fixed;verticalLabelPosition=bottom;verticalAlign=top;image=data:image/png,$b64;")
  $cell.SetAttribute('value', '')
  $cell.SetAttribute('vertex', '1')
  $geom = $doc.CreateElement('mxGeometry')
  $geom.SetAttribute('x', [string] $place[0])
  $geom.SetAttribute('y', [string] $place[1])
  $geom.SetAttribute('width', [string] $place[2])
  $geom.SetAttribute('height', [string] $place[3])
  $geom.SetAttribute('as', 'geometry')
  [void] $cell.AppendChild($geom)
  [void] $root.AppendChild($cell)
}

function Build-ContactSheet([array] $iconPaths) {
  [int] $tile = 72
  [int] $labelH = 18
  [int] $cols = 7
  [int] $rows = [Math]::Ceiling(([double] $iconPaths.Count) / ([double] $cols))
  [int] $sheetW = $cols * $tile
  [int] $sheetH = $rows * ($tile + $labelH)
  $sheet = New-Object System.Drawing.Bitmap($sheetW, $sheetH, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $g = [System.Drawing.Graphics]::FromImage($sheet)
  try {
    $g.Clear([System.Drawing.Color]::White)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $font = New-Object System.Drawing.Font('Arial', 7)
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(70, 70, 70))
    for ($i = 0; $i -lt $iconPaths.Count; $i++) {
      $path = $iconPaths[$i]
      $img = [System.Drawing.Image]::FromFile($path)
      try {
        $col = $i % $cols
        $row = [Math]::Floor($i / $cols)
        $x = $col * $tile
        $y = $row * ($tile + $labelH)
        $scale = [Math]::Min(50.0 / $img.Width, 50.0 / $img.Height)
        $w = [int]($img.Width * $scale)
        $h = [int]($img.Height * $scale)
        $g.DrawImage($img, $x + [int](($tile - $w) / 2), $y + 8 + [int]((50 - $h) / 2), $w, $h)
        $name = [IO.Path]::GetFileNameWithoutExtension($path)
        $g.DrawString($name, $font, $brush, $x + 2, $y + $tile)
      } finally {
        $img.Dispose()
      }
    }
    $font.Dispose()
    $brush.Dispose()
  } finally {
    $g.Dispose()
  }
  $sheetPath = Join-Path $iconDir '_contact_sheet.png'
  $sheet.Save($sheetPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $sheet.Dispose()
  return $sheetPath
}

$source = [System.Drawing.Image]::FromFile($sourceImage)
$saved = @()
try {
  foreach ($icon in $icons) {
    $saved += Save-Crop $source $icon
  }
} finally {
  $source.Dispose()
}

Copy-Item -LiteralPath $baseDrawio -Destination $outDrawio -Force
$drawioDoc = New-Object System.Xml.XmlDocument
$drawioDoc.PreserveWhitespace = $true
$drawioDoc.Load($outDrawio)
$drawioRoot = $drawioDoc.SelectSingleNode('//mxGraphModel/root')

# Remove the previous experimental icon layers.
$removeNodes = @($drawioDoc.SelectNodes("//mxCell[starts-with(@id, 'native-') or starts-with(@id, 'origicon-') or contains(@style, 'shape=image')]"))
foreach ($node in $removeNodes) {
  [void] $node.ParentNode.RemoveChild($node)
}

foreach ($icon in $icons) {
  $path = Join-Path $iconDir ($icon.id + '.png')
  Add-ImageCell $drawioDoc $drawioRoot $icon.id $path $icon.place
}

$settings = New-Object System.Xml.XmlWriterSettings
$settings.Indent = $true
$settings.NewLineChars = "`n"
$settings.Encoding = New-Object System.Text.UTF8Encoding($false)
$writer = [System.Xml.XmlWriter]::Create($outDrawio, $settings)
try {
  $drawioDoc.Save($writer)
} finally {
  $writer.Close()
}

$sheet = Build-ContactSheet $saved
Write-Host "Saved $($saved.Count) original-style icon crops to $iconDir"
Write-Host "Embedded original icons into $outDrawio"
Write-Host "Contact sheet: $sheet"
