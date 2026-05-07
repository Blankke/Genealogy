<#
执行四代曾孙查询的有索引/无索引性能对比。

使用示例：
  .\scripts\run_performance_compare.ps1 -Database genealogy -User genealogy_app -RootMemberId 1

说明：
  - 脚本会调用 database/performance_compare.sql。
  - SQL 内会临时删除并重建相关索引，仅建议在本地演示库运行。
#>

param(
    [string]$Database = "genealogy",
    [string]$User = "genealogy_app",
    [string]$DbHost = "127.0.0.1",
    [string]$Password = "genealogy_password",
    [int]$RootMemberId = 1
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

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

try {
    & $Psql -h $DbHost -U $User -d $Database -v root_member_id=$RootMemberId -f (Join-Path $Root "database\performance_compare.sql")
}
finally {
    $env:PGPASSWORD = $PreviousPgPassword
}
