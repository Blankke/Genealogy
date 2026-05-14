<#
Generate report assets for the genealogy database project.

Usage example:
  .\scripts\generate_report_assets.ps1 -Database genealogy -User genealogy_app

What this script produces:
  - SQL result screenshots
  - E-R diagram image
  - Performance comparison screenshots
  - Exported branch CSV for submission
#>

param(
    [string]$Database = "genealogy",
    [string]$User = "genealogy_app",
    [string]$DbHost = "127.0.0.1",
    [string]$Password = "genealogy_password",
    [string]$ScreenshotDir = "docs\report\screenshots",
    [string]$TextOutputDir = "docs\report\query_outputs",
    [string]$ExportOutput = "data\exports\branch_44829.csv",
    [string]$PerformanceSchema = "report_perf",
    [int]$BasicQueryMemberId = 6,
    [int]$AncestorQueryMemberId = 3590,
    [int]$GenealogyId = 1,
    [int]$PerformanceGenealogyId = 2,
    [int]$PerformanceRootMemberId = 52001,
    [int]$ResultPreviewRows = 12,
    [switch]$KeepPerformanceSchema
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ResolvedScreenshotDir = Join-Path $Root $ScreenshotDir
$ResolvedTextOutputDir = Join-Path $Root $TextOutputDir
$ResolvedExportPath = Join-Path $Root $ExportOutput

New-Item -ItemType Directory -Force -Path $ResolvedScreenshotDir, $ResolvedTextOutputDir | Out-Null
Add-Type -AssemblyName System.Drawing

function Resolve-Psql {
    $Command = Get-Command psql -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $Candidates = @(
        "D:\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\16\bin\psql.exe",
        "C:\Program Files\PostgreSQL\17\bin\psql.exe"
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path $Candidate) {
            return $Candidate
        }
    }

    throw "psql.exe not found. Install PostgreSQL or add PostgreSQL bin directory to PATH."
}

function Invoke-PsqlTextQuery {
    param(
        [string]$Psql,
        [string]$Sql
    )

    $TempPath = Join-Path $env:TEMP ("genealogy_report_text_{0}.txt" -f [guid]::NewGuid().ToString("N"))
    $PreviousPgPassword = $env:PGPASSWORD
    $PreviousClientEncoding = $env:PGCLIENTENCODING

    try {
        if ($Password) {
            $env:PGPASSWORD = $Password
        }
        $env:PGCLIENTENCODING = "UTF8"
        & $Psql -h $DbHost -U $User -d $Database -v ON_ERROR_STOP=1 -P pager=off -o $TempPath -c $Sql | Out-Null
        return Get-Content -LiteralPath $TempPath -Raw -Encoding UTF8
    }
    finally {
        if (Test-Path -LiteralPath $TempPath) {
            Remove-Item -LiteralPath $TempPath -Force
        }
        $env:PGPASSWORD = $PreviousPgPassword
        $env:PGCLIENTENCODING = $PreviousClientEncoding
    }
}

function Invoke-PsqlCsvQuery {
    param(
        [string]$Psql,
        [string]$Sql
    )

    $TempPath = Join-Path $env:TEMP ("genealogy_report_csv_{0}.csv" -f [guid]::NewGuid().ToString("N"))
    $PreviousPgPassword = $env:PGPASSWORD
    $PreviousClientEncoding = $env:PGCLIENTENCODING

    try {
        if ($Password) {
            $env:PGPASSWORD = $Password
        }
        $env:PGCLIENTENCODING = "UTF8"
        & $Psql -h $DbHost -U $User -d $Database -v ON_ERROR_STOP=1 --csv -o $TempPath -c $Sql | Out-Null

        $CsvLines = Get-Content -LiteralPath $TempPath -Encoding UTF8
        if (-not $CsvLines -or $CsvLines.Count -le 1) {
            return @()
        }
        return @($CsvLines | ConvertFrom-Csv)
    }
    finally {
        if (Test-Path -LiteralPath $TempPath) {
            Remove-Item -LiteralPath $TempPath -Force
        }
        $env:PGPASSWORD = $PreviousPgPassword
        $env:PGCLIENTENCODING = $PreviousClientEncoding
    }
}

function Invoke-PsqlNonQuery {
    param(
        [string]$Psql,
        [string]$Sql
    )

    $PreviousPgPassword = $env:PGPASSWORD
    $PreviousClientEncoding = $env:PGCLIENTENCODING

    try {
        if ($Password) {
            $env:PGPASSWORD = $Password
        }
        $env:PGCLIENTENCODING = "UTF8"
        & $Psql -h $DbHost -U $User -d $Database -v ON_ERROR_STOP=1 -c $Sql | Out-Null
    }
    finally {
        $env:PGPASSWORD = $PreviousPgPassword
        $env:PGCLIENTENCODING = $PreviousClientEncoding
    }
}

function Save-TextFile {
    param(
        [string]$Path,
        [string]$Content
    )

    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

function Convert-ResultRowsToText {
    param(
        [string]$Title,
        [array]$Rows,
        [int]$PreviewRows,
        [string[]]$ExtraLines = @()
    )

    $AllRows = @($Rows)
    $DisplayRows = if ($PreviewRows -gt 0) { @($AllRows | Select-Object -First $PreviewRows) } else { @($AllRows) }
    $AllRowCount = @($AllRows).Count
    $DisplayRowCount = @($DisplayRows).Count

    if ($DisplayRowCount -gt 0) {
        $TableText = ($DisplayRows | Format-Table -AutoSize | Out-String -Width 400).TrimEnd()
    }
    else {
        $TableText = "(0 rows)"
    }

    $Lines = @(
        "PostgreSQL 16.13 > $Title",
        "",
        $TableText,
        "",
        ("Total rows: {0}" -f $AllRowCount)
    )

    if ($AllRowCount -gt $DisplayRowCount) {
        $Lines += ("Preview rows: first {0}" -f $PreviewRows)
    }

    if ($ExtraLines.Count -gt 0) {
        $Lines += $ExtraLines
    }

    return ($Lines -join "`r`n")
}

function Save-TerminalScreenshot {
    param(
        [string]$Text,
        [string]$Path
    )

    $Lines = $Text -split "`r?`n"
    $Font = New-Object System.Drawing.Font("Consolas", 13)
    $HeaderFont = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
    $Padding = 24
    $HeaderHeight = 40

    $MeasureBitmap = New-Object System.Drawing.Bitmap 1, 1
    $MeasureGraphics = [System.Drawing.Graphics]::FromImage($MeasureBitmap)
    $MeasureGraphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

    $MaxWidth = 0
    foreach ($Line in $Lines) {
        $MeasuredWidth = [math]::Ceiling($MeasureGraphics.MeasureString($Line, $Font).Width)
        if ($MeasuredWidth -gt $MaxWidth) {
            $MaxWidth = $MeasuredWidth
        }
    }

    $LineHeight = [math]::Ceiling($Font.GetHeight($MeasureGraphics)) + 4
    $ImageWidth = [math]::Max(1200, $MaxWidth + ($Padding * 2))
    $ImageHeight = $HeaderHeight + ($Padding * 2) + ($LineHeight * [math]::Max(1, $Lines.Count))

    $MeasureGraphics.Dispose()
    $MeasureBitmap.Dispose()

    $Bitmap = New-Object System.Drawing.Bitmap $ImageWidth, $ImageHeight
    $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
    $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $Graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

    $BackgroundBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(13, 17, 23))
    $HeaderBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(22, 27, 34))
    $TextBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(201, 209, 217))
    $AccentBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(86, 156, 214))
    $CircleBrushes = @(
        (New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 95, 86))),
        (New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 189, 46))),
        (New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(39, 201, 63)))
    )

    try {
        $Graphics.FillRectangle($BackgroundBrush, 0, 0, $ImageWidth, $ImageHeight)
        $Graphics.FillRectangle($HeaderBrush, 0, 0, $ImageWidth, $HeaderHeight)
        $Graphics.DrawString("SQL result screenshot", $HeaderFont, $AccentBrush, 80, 9)

        $CircleX = 20
        foreach ($Brush in $CircleBrushes) {
            $Graphics.FillEllipse($Brush, $CircleX, 13, 12, 12)
            $CircleX += 18
        }

        $Y = $HeaderHeight + $Padding
        foreach ($Line in $Lines) {
            $Graphics.DrawString($Line, $Font, $TextBrush, $Padding, $Y)
            $Y += $LineHeight
        }

        $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        foreach ($Brush in $CircleBrushes) {
            $Brush.Dispose()
        }
        $BackgroundBrush.Dispose()
        $HeaderBrush.Dispose()
        $TextBrush.Dispose()
        $AccentBrush.Dispose()
        $Font.Dispose()
        $HeaderFont.Dispose()
        $Graphics.Dispose()
        $Bitmap.Dispose()
    }
}

function Save-ErDiagram {
    param(
        [string]$Path
    )

    $Width = 1900
    $Height = 1220
    $Bitmap = New-Object System.Drawing.Bitmap $Width, $Height
    $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
    $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality

    $BackgroundBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $TitleBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(17, 24, 39))
    $EntityBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(243, 244, 246))
    $HeaderBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(30, 64, 175))
    $HeaderTextBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $BodyTextBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(31, 41, 55))
    $RelationBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(75, 85, 99))
    $LinePen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(75, 85, 99), 2)
    $BorderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(209, 213, 219), 1)
    $TitleFont = New-Object System.Drawing.Font("Segoe UI", 20, [System.Drawing.FontStyle]::Bold)
    $EntityTitleFont = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Bold)
    $EntityBodyFont = New-Object System.Drawing.Font("Segoe UI", 12)
    $RelationFont = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)

    function Draw-EntityBox {
        param(
            [System.Drawing.Graphics]$Canvas,
            [System.Drawing.Rectangle]$Rect,
            [string]$Title,
            [string[]]$Lines
        )

        $Canvas.FillRectangle($EntityBrush, $Rect)
        $Canvas.DrawRectangle($BorderPen, $Rect)

        $HeaderRect = New-Object System.Drawing.Rectangle $Rect.X, $Rect.Y, $Rect.Width, 42
        $Canvas.FillRectangle($HeaderBrush, $HeaderRect)
        $Canvas.DrawString($Title, $EntityTitleFont, $HeaderTextBrush, $Rect.X + 14, $Rect.Y + 8)

        $YOffset = $Rect.Y + 56
        foreach ($Line in $Lines) {
            $Canvas.DrawString($Line, $EntityBodyFont, $BodyTextBrush, $Rect.X + 14, $YOffset)
            $YOffset += 24
        }
    }

    function Draw-Relation {
        param(
            [System.Drawing.Graphics]$Canvas,
            [int]$X1,
            [int]$Y1,
            [int]$X2,
            [int]$Y2,
            [string]$Label,
            [int]$LabelX,
            [int]$LabelY
        )

        $Canvas.DrawLine($LinePen, $X1, $Y1, $X2, $Y2)
        $Canvas.DrawString($Label, $RelationFont, $RelationBrush, $LabelX, $LabelY)
    }

    try {
        $Graphics.FillRectangle($BackgroundBrush, 0, 0, $Width, $Height)
        $Graphics.DrawString("genealogy E-R diagram", $TitleFont, $TitleBrush, 40, 30)

        $UsersRect = New-Object System.Drawing.Rectangle 70, 120, 320, 190
        $GenealogiesRect = New-Object System.Drawing.Rectangle 640, 120, 360, 210
        $CollaboratorsRect = New-Object System.Drawing.Rectangle 1160, 120, 420, 210
        $MembersRect = New-Object System.Drawing.Rectangle 640, 500, 380, 230
        $ParentChildRect = New-Object System.Drawing.Rectangle 120, 860, 500, 210
        $MarriagesRect = New-Object System.Drawing.Rectangle 1120, 860, 430, 210

        Draw-EntityBox -Canvas $Graphics -Rect $UsersRect -Title "users" -Lines @(
            "PK id",
            "username",
            "email",
            "password_hash",
            "is_admin",
            "created_at"
        )
        Draw-EntityBox -Canvas $Graphics -Rect $GenealogiesRect -Title "genealogies" -Lines @(
            "PK id",
            "name",
            "surname",
            "revision_time",
            "FK owner_user_id -> users.id",
            "created_at"
        )
        Draw-EntityBox -Canvas $Graphics -Rect $CollaboratorsRect -Title "genealogy_collaborators" -Lines @(
            "PK id",
            "FK genealogy_id -> genealogies.id",
            "FK user_id -> users.id",
            "role",
            "invited_at",
            "UNIQUE(genealogy_id, user_id)"
        )
        Draw-EntityBox -Canvas $Graphics -Rect $MembersRect -Title "members" -Lines @(
            "PK id",
            "FK genealogy_id -> genealogies.id",
            "name / gender",
            "birth_date / death_date",
            "generation_index",
            "biography / created_at"
        )
        Draw-EntityBox -Canvas $Graphics -Rect $ParentChildRect -Title "parent_child_relations" -Lines @(
            "PK id",
            "FK genealogy_id -> genealogies.id",
            "FK parent_id -> members.id",
            "FK child_id -> members.id",
            "parent_role",
            "UNIQUE(parent_id, child_id, parent_role)"
        )
        Draw-EntityBox -Canvas $Graphics -Rect $MarriagesRect -Title "marriages" -Lines @(
            "PK id",
            "FK genealogy_id -> genealogies.id",
            "FK spouse_a_id -> members.id",
            "FK spouse_b_id -> members.id",
            "start_date / end_date",
            "status"
        )

        Draw-Relation -Canvas $Graphics -X1 390 -Y1 200 -X2 640 -Y2 200 -Label "1 : N creates" -LabelX 455 -LabelY 170
        Draw-Relation -Canvas $Graphics -X1 325 -Y1 270 -X2 1160 -Y2 270 -Label "1 : N joins" -LabelX 720 -LabelY 240
        Draw-Relation -Canvas $Graphics -X1 1000 -Y1 250 -X2 1160 -Y2 250 -Label "1 : N invites" -LabelX 1030 -LabelY 215
        Draw-Relation -Canvas $Graphics -X1 820 -Y1 330 -X2 820 -Y2 500 -Label "1 : N contains" -LabelX 850 -LabelY 395
        Draw-Relation -Canvas $Graphics -X1 740 -Y1 730 -X2 460 -Y2 860 -Label "1 : N parent" -LabelX 570 -LabelY 770
        Draw-Relation -Canvas $Graphics -X1 900 -Y1 730 -X2 620 -Y2 860 -Label "1 : N child" -LabelX 820 -LabelY 785
        Draw-Relation -Canvas $Graphics -X1 1020 -Y1 620 -X2 1120 -Y2 920 -Label "1 : N spouse A/B" -LabelX 1045 -LabelY 760

        $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $BackgroundBrush.Dispose()
        $TitleBrush.Dispose()
        $EntityBrush.Dispose()
        $HeaderBrush.Dispose()
        $HeaderTextBrush.Dispose()
        $BodyTextBrush.Dispose()
        $RelationBrush.Dispose()
        $LinePen.Dispose()
        $BorderPen.Dispose()
        $TitleFont.Dispose()
        $EntityTitleFont.Dispose()
        $EntityBodyFont.Dispose()
        $RelationFont.Dispose()
        $Graphics.Dispose()
        $Bitmap.Dispose()
    }
}

function Write-StepProgress {
    param(
        [int]$Index,
        [int]$Total,
        [string]$Activity
    )

    $Percent = [math]::Floor(($Index / $Total) * 100)
    Write-Progress -Activity "Generate report assets" -Status $Activity -PercentComplete $Percent
}

$Psql = Resolve-Psql
$TotalSteps = 10
$CurrentStep = 0

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Generate E-R diagram"
$ErDiagramPath = Join-Path $ResolvedScreenshotDir "er_diagram.png"
Save-ErDiagram -Path $ErDiagramPath

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Collect environment data"
$EnvironmentText = Invoke-PsqlTextQuery -Psql $Psql -Sql @"
SELECT current_database() AS database_name, current_user AS db_user, version() AS db_version;
SELECT genealogy_id, COUNT(*) AS member_count
FROM members
GROUP BY genealogy_id
ORDER BY genealogy_id;
"@
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "00_environment.txt") -Content $EnvironmentText

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Render query 1"
$Query1Rows = Invoke-PsqlCsvQuery -Psql $Psql -Sql @"
WITH target AS (
    SELECT CAST($BasicQueryMemberId AS BIGINT) AS member_id
),
spouses AS (
    SELECT
        CASE WHEN m.spouse_a_id = target.member_id THEN m.spouse_b_id ELSE m.spouse_a_id END AS related_member_id,
        'spouse' AS relation_type
    FROM marriages m
    JOIN target ON target.member_id IN (m.spouse_a_id, m.spouse_b_id)
),
children AS (
    SELECT child_id AS related_member_id, 'child' AS relation_type
    FROM parent_child_relations pcr
    JOIN target ON target.member_id = pcr.parent_id
)
SELECT r.relation_type, mem.*
FROM (
    SELECT * FROM spouses
    UNION ALL
    SELECT * FROM children
) r
JOIN members mem ON mem.id = r.related_member_id
ORDER BY r.relation_type, mem.birth_date NULLS LAST, mem.id;
"@
$Query1Text = Convert-ResultRowsToText -Title "Query 1: spouse and children for member $BasicQueryMemberId" -Rows $Query1Rows -PreviewRows $ResultPreviewRows
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "01_family_query.txt") -Content $Query1Text
Save-TerminalScreenshot -Text $Query1Text -Path (Join-Path $ResolvedScreenshotDir "01_family_query.png")

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Render query 2"
$Query2Rows = Invoke-PsqlCsvQuery -Psql $Psql -Sql @"
WITH RECURSIVE ancestors AS (
    SELECT
        pcr.parent_id AS member_id,
        pcr.child_id,
        pcr.parent_role,
        1 AS depth,
        ARRAY[CAST(pcr.child_id AS BIGINT), CAST(pcr.parent_id AS BIGINT)] AS path
    FROM parent_child_relations pcr
    WHERE pcr.child_id = CAST($AncestorQueryMemberId AS BIGINT)
    UNION ALL
    SELECT
        pcr.parent_id,
        pcr.child_id,
        pcr.parent_role,
        ancestors.depth + 1,
        ancestors.path || pcr.parent_id
    FROM parent_child_relations pcr
    JOIN ancestors ON ancestors.member_id = pcr.child_id
    WHERE NOT pcr.parent_id = ANY(ancestors.path)
),
minimum_depth AS (
    SELECT member_id, MIN(depth) AS depth
    FROM ancestors
    GROUP BY member_id
),
summarized AS (
    SELECT
        ancestors.member_id,
        minimum_depth.depth,
        ARRAY_AGG(DISTINCT ancestors.parent_role ORDER BY ancestors.parent_role)
            FILTER (WHERE ancestors.depth = minimum_depth.depth) AS parent_roles,
        COUNT(*) FILTER (WHERE ancestors.depth = minimum_depth.depth) AS path_count
    FROM ancestors
    JOIN minimum_depth ON minimum_depth.member_id = ancestors.member_id
    GROUP BY ancestors.member_id, minimum_depth.depth
)
SELECT
    summarized.depth,
    summarized.parent_roles,
    summarized.path_count,
    summarized.parent_roles[1] AS parent_role,
    members.*
FROM summarized
JOIN members ON members.id = summarized.member_id
ORDER BY summarized.depth, members.id;
"@
$Query2Text = Convert-ResultRowsToText -Title "Query 2: recursive ancestor query for member $AncestorQueryMemberId" -Rows $Query2Rows -PreviewRows $ResultPreviewRows
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "02_ancestor_query.txt") -Content $Query2Text
Save-TerminalScreenshot -Text $Query2Text -Path (Join-Path $ResolvedScreenshotDir "02_ancestor_query.png")

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Render query 3"
$Query3Rows = Invoke-PsqlCsvQuery -Psql $Psql -Sql @"
SELECT
    generation_index,
    ROUND(AVG(EXTRACT(YEAR FROM age(death_date, birth_date)))::NUMERIC, 2) AS average_lifespan_years,
    COUNT(*) AS sample_count
FROM members
WHERE genealogy_id = CAST($GenealogyId AS BIGINT)
  AND birth_date IS NOT NULL
  AND death_date IS NOT NULL
GROUP BY generation_index
ORDER BY average_lifespan_years DESC, sample_count DESC
LIMIT 1;
"@
$Query3Text = Convert-ResultRowsToText -Title "Query 3: generation with highest average lifespan in genealogy $GenealogyId" -Rows $Query3Rows -PreviewRows $ResultPreviewRows
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "03_generation_lifespan.txt") -Content $Query3Text
Save-TerminalScreenshot -Text $Query3Text -Path (Join-Path $ResolvedScreenshotDir "03_generation_lifespan.png")

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Render query 4"
$Query4Rows = Invoke-PsqlCsvQuery -Psql $Psql -Sql @"
SELECT members.*
FROM members
WHERE gender = 'male'
  AND birth_date IS NOT NULL
  AND birth_date <= CURRENT_DATE - INTERVAL '50 years'
  AND NOT EXISTS (
      SELECT 1
      FROM marriages
      WHERE members.id IN (marriages.spouse_a_id, marriages.spouse_b_id)
  )
ORDER BY birth_date, id;
"@
$Query4Text = Convert-ResultRowsToText -Title "Query 4: male members older than 50 without spouse" -Rows $Query4Rows -PreviewRows $ResultPreviewRows
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "04_unmarried_male_over_50.txt") -Content $Query4Text
Save-TerminalScreenshot -Text $Query4Text -Path (Join-Path $ResolvedScreenshotDir "04_unmarried_male_over_50.png")

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Render query 5"
$Query5Rows = Invoke-PsqlCsvQuery -Psql $Psql -Sql @"
WITH generation_average AS (
    SELECT
        genealogy_id,
        generation_index,
        AVG(EXTRACT(YEAR FROM birth_date)) AS average_birth_year
    FROM members
    WHERE genealogy_id = CAST($GenealogyId AS BIGINT)
      AND birth_date IS NOT NULL
    GROUP BY genealogy_id, generation_index
)
SELECT members.*, generation_average.average_birth_year
FROM members
JOIN generation_average
  ON generation_average.genealogy_id = members.genealogy_id
 AND generation_average.generation_index = members.generation_index
WHERE members.birth_date IS NOT NULL
  AND EXTRACT(YEAR FROM members.birth_date) < generation_average.average_birth_year
ORDER BY members.generation_index, members.birth_date, members.id;
"@
$Query5Text = Convert-ResultRowsToText -Title "Query 5: members born earlier than generation average year" -Rows $Query5Rows -PreviewRows $ResultPreviewRows
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "05_birth_before_generation_avg.txt") -Content $Query5Text
Save-TerminalScreenshot -Text $Query5Text -Path (Join-Path $ResolvedScreenshotDir "05_birth_before_generation_avg.png")

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Run performance comparison"
Invoke-PsqlNonQuery -Psql $Psql -Sql @"
DROP SCHEMA IF EXISTS $PerformanceSchema CASCADE;
CREATE SCHEMA $PerformanceSchema;
CREATE TABLE $PerformanceSchema.members AS
SELECT * FROM members WHERE genealogy_id = $PerformanceGenealogyId;
CREATE TABLE $PerformanceSchema.parent_child_relations AS
SELECT * FROM parent_child_relations WHERE genealogy_id = $PerformanceGenealogyId;
CREATE UNIQUE INDEX ${PerformanceSchema}_members_id_idx ON $PerformanceSchema.members (id);
ANALYZE $PerformanceSchema.members;
ANALYZE $PerformanceSchema.parent_child_relations;
"@

$PerformanceQuery = @"
EXPLAIN (ANALYZE, BUFFERS)
SELECT great_grandchild.*
FROM $PerformanceSchema.parent_child_relations p1
JOIN $PerformanceSchema.parent_child_relations p2 ON p2.parent_id = p1.child_id
JOIN $PerformanceSchema.parent_child_relations p3 ON p3.parent_id = p2.child_id
JOIN $PerformanceSchema.members great_grandchild ON great_grandchild.id = p3.child_id
WHERE p1.parent_id = $PerformanceRootMemberId;
"@

$PerformanceWithoutIndexText = Invoke-PsqlTextQuery -Psql $Psql -Sql $PerformanceQuery
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "06_performance_without_index.txt") -Content $PerformanceWithoutIndexText
Save-TerminalScreenshot -Text ("PostgreSQL 16.13 > Performance without designed indexes`r`n`r`n" + $PerformanceWithoutIndexText.TrimEnd()) -Path (Join-Path $ResolvedScreenshotDir "06_performance_without_index.png")

Invoke-PsqlNonQuery -Psql $Psql -Sql @"
CREATE INDEX idx_parent_child_parent ON $PerformanceSchema.parent_child_relations (parent_id);
CREATE INDEX idx_parent_child_genealogy_parent ON $PerformanceSchema.parent_child_relations (genealogy_id, parent_id);
ANALYZE $PerformanceSchema.parent_child_relations;
"@

$PerformanceWithIndexText = Invoke-PsqlTextQuery -Psql $Psql -Sql $PerformanceQuery
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "07_performance_with_index.txt") -Content $PerformanceWithIndexText
Save-TerminalScreenshot -Text ("PostgreSQL 16.13 > Performance with designed indexes`r`n`r`n" + $PerformanceWithIndexText.TrimEnd()) -Path (Join-Path $ResolvedScreenshotDir "07_performance_with_index.png")

if (-not $KeepPerformanceSchema) {
    Invoke-PsqlNonQuery -Psql $Psql -Sql "DROP SCHEMA IF EXISTS $PerformanceSchema CASCADE;"
}

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Export branch CSV"
& (Join-Path $Root "scripts\export_branch.ps1") -Database $Database -User $User -DbHost $DbHost -Password $Password -RootMemberId 44829 -Output $ExportOutput | Out-Null

Write-StepProgress -Index ($CurrentStep += 1) -Total $TotalSteps -Activity "Write manifest"
$ManifestText = @"
Generated assets:
- ER diagram: $ErDiagramPath
- Screenshot dir: $ResolvedScreenshotDir
- Text output dir: $ResolvedTextOutputDir
- Exported branch file: $ResolvedExportPath

Default demo parameters:
- Query 1 member id: $BasicQueryMemberId
- Query 2 member id: $AncestorQueryMemberId
- Query 3/5 genealogy id: $GenealogyId
- Performance genealogy id: $PerformanceGenealogyId
- Performance root member id: $PerformanceRootMemberId
- Export root member id: 44829
"@
Save-TextFile -Path (Join-Path $ResolvedTextOutputDir "README_report_assets.txt") -Content $ManifestText.Trim()

Write-Progress -Activity "Generate report assets" -Completed
Write-Output $ManifestText.Trim()
