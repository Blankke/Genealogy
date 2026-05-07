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
    [int]$RootMemberId = 1
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
psql -U $User -d $Database -v root_member_id=$RootMemberId -f (Join-Path $Root "database\performance_compare.sql")
