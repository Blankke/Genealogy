<# 
导入族谱 CSV 数据到本地 PostgreSQL。

使用示例：
  .\scripts\import_csv.ps1 -Database genealogy -User genealogy_app -DataDir data\generated -Reset

说明：
  - 运行前请确认 psql 已加入 PATH。
  - -Reset 会清空业务表并重置自增 ID，适合本地演示环境。
#>

param(
    [string]$Database = "genealogy",
    [string]$User = "genealogy_app",
    [string]$DbHost = "127.0.0.1",
    [string]$Password = "genealogy_password",
    [string]$DataDir = "data\generated",
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$ResolvedDataDir = Resolve-Path (Join-Path $Root $DataDir)

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

$ImportSql = New-TemporaryFile
try {
    & $Psql -h $DbHost -U $User -d $Database -f (Join-Path $Root "database\schema.sql")
    & $Psql -h $DbHost -U $User -d $Database -f (Join-Path $Root "database\indexes.sql")

    $Lines = @()
    if ($Reset) {
        $Lines += "TRUNCATE marriages, parent_child_relations, members, genealogy_collaborators, genealogies, users RESTART IDENTITY CASCADE;"
    }
    $Lines += "\copy users(id, username, email, password_hash, is_admin, created_at) FROM '$($ResolvedDataDir.Path)\users.csv' WITH (FORMAT csv, HEADER true)"
    $Lines += "\copy genealogies(id, name, surname, revision_time, owner_user_id, created_at) FROM '$($ResolvedDataDir.Path)\genealogies.csv' WITH (FORMAT csv, HEADER true)"
    $Lines += "\copy genealogy_collaborators(id, genealogy_id, user_id, role, invited_at) FROM '$($ResolvedDataDir.Path)\genealogy_collaborators.csv' WITH (FORMAT csv, HEADER true)"
    $Lines += "\copy members(id, genealogy_id, name, gender, birth_date, death_date, generation_index, biography, created_at) FROM '$($ResolvedDataDir.Path)\members.csv' WITH (FORMAT csv, HEADER true)"
    $Lines += "\copy parent_child_relations(id, genealogy_id, parent_id, child_id, parent_role, created_at) FROM '$($ResolvedDataDir.Path)\parent_child_relations.csv' WITH (FORMAT csv, HEADER true)"
    $Lines += "\copy marriages(id, genealogy_id, spouse_a_id, spouse_b_id, start_date, end_date, status, created_at) FROM '$($ResolvedDataDir.Path)\marriages.csv' WITH (FORMAT csv, HEADER true)"
    $Lines += "SELECT setval(pg_get_serial_sequence('users','id'), COALESCE((SELECT MAX(id) FROM users), 1));"
    $Lines += "SELECT setval(pg_get_serial_sequence('genealogies','id'), COALESCE((SELECT MAX(id) FROM genealogies), 1));"
    $Lines += "SELECT setval(pg_get_serial_sequence('members','id'), COALESCE((SELECT MAX(id) FROM members), 1));"
    Set-Content -Path $ImportSql -Value $Lines -Encoding UTF8
    & $Psql -h $DbHost -U $User -d $Database -f $ImportSql
}
finally {
    Remove-Item -LiteralPath $ImportSql -Force
    $env:PGPASSWORD = $PreviousPgPassword
}
