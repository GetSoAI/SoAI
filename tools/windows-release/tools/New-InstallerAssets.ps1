[CmdletBinding()]
param(
    [string]$AssetsDir,
    [string]$LogoPath
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($AssetsDir)) {
    $AssetsDir = Join-Path $PSScriptRoot '..\installer\assets'
}

function Resolve-FullPath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $executionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
}

function Resolve-LogoPath {
    param([string]$ExplicitPath)
    if (![string]::IsNullOrWhiteSpace($ExplicitPath)) {
        $resolved = Resolve-FullPath $ExplicitPath
        if (!(Test-Path -LiteralPath $resolved)) {
            throw "SoAI installer logo was not found: $resolved"
        }
        return $resolved
    }

    $candidates = @(
        (Join-Path $PSScriptRoot '..\..\frontend\assets\img\soai\soai-logo-small-dark.png'),
        (Join-Path $PSScriptRoot '..\..\frontend\android-chrome-512x512.png')
    )
    foreach ($candidate in $candidates) {
        $resolved = Resolve-FullPath $candidate
        if (Test-Path -LiteralPath $resolved) {
            return $resolved
        }
    }

    throw 'SoAI installer logo was not found. Pass -LogoPath pointing to frontend\assets\img\soai\soai-logo-small-dark.png.'
}

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

function Draw-CenteredImage {
    param(
        [Parameter(Mandatory=$true)][System.Drawing.Graphics]$Graphics,
        [Parameter(Mandatory=$true)][System.Drawing.Image]$Image,
        [Parameter(Mandatory=$true)][System.Drawing.RectangleF]$Bounds
    )
    $scale = [Math]::Min($Bounds.Width / $Image.Width, $Bounds.Height / $Image.Height)
    $width = $Image.Width * $scale
    $height = $Image.Height * $scale
    $x = $Bounds.X + (($Bounds.Width - $width) / 2)
    $y = $Bounds.Y + (($Bounds.Height - $height) / 2)
    $Graphics.DrawImage($Image, [System.Drawing.RectangleF]::new($x, $y, $width, $height))
}

function New-WelcomeBitmap {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][System.Drawing.Image]$Logo
    )
    $bitmap = [System.Drawing.Bitmap]::new(164, 314)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.Clear([System.Drawing.Color]::FromArgb(21, 21, 21))

        $accent = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(242, 142, 43))
        $white = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
        $titleFont = [System.Drawing.Font]::new('Segoe UI', 22, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
        try {
            $graphics.FillRectangle($accent, 0, 0, 10, 314)
            Draw-CenteredImage -Graphics $graphics -Image $Logo -Bounds ([System.Drawing.RectangleF]::new(32, 32, 100, 100))
            $graphics.DrawString('SoAI', $titleFont, $white, 32, 146)
        }
        finally {
            $titleFont.Dispose()
            $white.Dispose()
            $accent.Dispose()
        }
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Bmp)
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function New-HeaderBitmap {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][System.Drawing.Image]$Logo
    )
    $bitmap = [System.Drawing.Bitmap]::new(150, 57)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.Clear([System.Drawing.Color]::White)

        $textBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(21, 21, 21))
        $titleFont = [System.Drawing.Font]::new('Segoe UI', 20, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
        try {
            Draw-CenteredImage -Graphics $graphics -Image $Logo -Bounds ([System.Drawing.RectangleF]::new(8, 6, 44, 44))
            $graphics.DrawString('SoAI', $titleFont, $textBrush, 58, 15)
        }
        finally {
            $titleFont.Dispose()
            $textBrush.Dispose()
        }
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Bmp)
    }
    finally {
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

function New-IconAsset {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][System.Drawing.Image]$Logo
    )
    $entries = @()
    foreach ($size in @(16, 20, 24, 32, 40, 48, 64, 128, 256)) {
        $bitmap = [System.Drawing.Bitmap]::new($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
            $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
            $graphics.Clear([System.Drawing.Color]::Transparent)
            Draw-CenteredImage -Graphics $graphics -Image $Logo -Bounds ([System.Drawing.RectangleF]::new(0, 0, $size, $size))
        }
        finally {
            $graphics.Dispose()
        }
        try {
            $entries += @{
                Size = $size
                Bytes = Convert-BitmapToIconDibBytes -Bitmap $bitmap
            }
        }
        finally {
            $bitmap.Dispose()
        }
    }

    Write-MultiResolutionIcon -Path $Path -Entries $entries
}

function Convert-BitmapToIconDibBytes {
    param([Parameter(Mandatory=$true)][System.Drawing.Bitmap]$Bitmap)
    $width = $Bitmap.Width
    $height = $Bitmap.Height
    $xorBytes = New-Object byte[] ($width * $height * 4)
    $offset = 0
    for ($y = $height - 1; $y -ge 0; $y -= 1) {
        for ($x = 0; $x -lt $width; $x += 1) {
            $pixel = $Bitmap.GetPixel($x, $y)
            $xorBytes[$offset] = $pixel.B
            $xorBytes[$offset + 1] = $pixel.G
            $xorBytes[$offset + 2] = $pixel.R
            $xorBytes[$offset + 3] = $pixel.A
            $offset += 4
        }
    }

    $maskStride = [int]([Math]::Ceiling($width / 32.0) * 4)
    $maskBytes = New-Object byte[] ($maskStride * $height)
    $stream = [System.IO.MemoryStream]::new()
    $writer = [System.IO.BinaryWriter]::new($stream)
    try {
        $writer.Write([UInt32]40)
        $writer.Write([Int32]$width)
        $writer.Write([Int32]($height * 2))
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]32)
        $writer.Write([UInt32]0)
        $writer.Write([UInt32]($xorBytes.Length))
        $writer.Write([Int32]0)
        $writer.Write([Int32]0)
        $writer.Write([UInt32]0)
        $writer.Write([UInt32]0)
        $writer.Write($xorBytes)
        $writer.Write($maskBytes)
        $writer.Flush()
        return $stream.ToArray()
    }
    finally {
        $writer.Dispose()
        $stream.Dispose()
    }
}

function Write-MultiResolutionIcon {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][object[]]$Entries
    )
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
    $writer = [System.IO.BinaryWriter]::new($stream)
    try {
        $writer.Write([UInt16]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]$Entries.Count)
        $imageOffset = 6 + (16 * $Entries.Count)
        foreach ($entry in $Entries) {
            $size = [int]$entry.Size
            $bytes = [byte[]]$entry.Bytes
            $encodedSize = [byte]0
            if ($size -eq 256) {
                $encodedSize = [byte]0
            }
            else {
                $encodedSize = [byte]$size
            }
            $writer.Write($encodedSize)
            $writer.Write($encodedSize)
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            $writer.Write([UInt16]1)
            $writer.Write([UInt16]32)
            $writer.Write([UInt32]$bytes.Length)
            $writer.Write([UInt32]$imageOffset)
            $imageOffset += $bytes.Length
        }
        foreach ($entry in $Entries) {
            $writer.Write([byte[]]$entry.Bytes)
        }
    }
    finally {
        $writer.Dispose()
        $stream.Dispose()
    }
}

$assetsRoot = Resolve-FullPath $AssetsDir
$sourceLogo = Resolve-LogoPath -ExplicitPath $LogoPath
New-Item -ItemType Directory -Force -Path $assetsRoot | Out-Null

$logo = [System.Drawing.Image]::FromFile($sourceLogo)
try {
    if ($logo.Width -ne $logo.Height) {
        throw "SoAI installer logo must be square. Got $($logo.Width)x$($logo.Height): $sourceLogo"
    }
    New-WelcomeBitmap -Path (Join-Path $assetsRoot 'welcome.bmp') -Logo $logo
    New-HeaderBitmap -Path (Join-Path $assetsRoot 'header.bmp') -Logo $logo
    New-IconAsset -Path (Join-Path $assetsRoot 'soai-installer.ico') -Logo $logo
}
finally {
    $logo.Dispose()
}

Write-Host "Installer assets written to: $assetsRoot"
