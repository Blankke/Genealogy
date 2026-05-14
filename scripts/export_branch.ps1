<#
导出某个成员的直系后代分支 CSV。

使用示例：
  .\scripts\export_branch.ps1 -Database genealogy -User genealogy_app -RootMemberId 1 -Output data\exports\branch_1.csv

说明：
  - 运行前请确认 psql 已加入 PATH。
  - 输出文件位于 data/exports/，默认已被 .gitignore 忽略。
#>

param(
    [string]$Database = "genealogy",
    [string]$User = "genealogy_app",
    [string]$DbHost = "127.0.0.1",
    [string]$Password = "genealogy_password",
    [int]$RootMemberId = 1,
    [string]$Output = "data\exports\branch.csv"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$OutputPath = Join-Path $Root $Output
$OutputDir = Split-Path $OutputPath
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$TemporaryOutputPath = Join-Path $env:TEMP ("genealogy_branch_export_{0}.csv" -f [guid]::NewGuid().ToString("N"))
$OutputPathForPsql = ($TemporaryOutputPath -replace "\\", "/") -replace "'", "''"

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

$Psql = Resolve-Psql
$PreviousPgPassword = $env:PGPASSWORD
if ($Password) {
    $env:PGPASSWORD = $Password
}

$ExportSql = New-TemporaryFile
try {
    $Query = "\copy (WITH RECURSIVE root AS (SELECT id AS member_id, genealogy_id FROM members WHERE id = $RootMemberId::BIGINT), branch AS (SELECT member_id, genealogy_id FROM root UNION SELECT pcr.child_id, branch.genealogy_id FROM parent_child_relations pcr JOIN branch ON branch.member_id = pcr.parent_id AND pcr.genealogy_id = branch.genealogy_id) SELECT members.* FROM members JOIN branch ON branch.member_id = members.id AND branch.genealogy_id = members.genealogy_id ORDER BY members.generation_index, members.id) TO '$OutputPathForPsql' WITH (FORMAT csv, HEADER true)"
    Set-Content -Path $ExportSql -Value $Query -Encoding UTF8
    & $Psql -h $DbHost -U $User -d $Database -f $ExportSql
    Move-Item -LiteralPath $TemporaryOutputPath -Destination $OutputPath -Force
}
finally {
    Remove-Item -LiteralPath $ExportSql -Force
    if (Test-Path -LiteralPath $TemporaryOutputPath) {
        Remove-Item -LiteralPath $TemporaryOutputPath -Force
    }
    $env:PGPASSWORD = $PreviousPgPassword
}
