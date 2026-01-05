from pathlib import Path

import pytest
from openpyxl import Workbook

from tools.vuln_classifier.vuln_classifier import (
    AppConfig,
    ColumnMapping,
    SystemConfig,
    build_records,
    parse_plugin_output_pairs,
    read_vuln_records_from_excel,
    summarize_by_system,
    summarize_by_system_service,
    summarize_by_system_iap_service_subpackage,
)


def test_parse_plugin_output_ok() -> None:
    text = "xxx\nSpringBoot项目包路径：/home/订单服务/springboot/abc\nSpringBoot子包名称：order.jar\nzzz"
    pairs, ok = parse_plugin_output_pairs(text)
    assert ok is True
    assert pairs == [("订单服务", "order.jar")]


def test_parse_plugin_output_fallback() -> None:
    text = "完全不包含关键字"
    pairs, ok = parse_plugin_output_pairs(text)
    assert ok is False
    assert pairs == [("其他", text)]


def test_parse_plugin_output_multi_dedupe() -> None:
    text = "\n".join(
        [
            "SpringBoot项目包路径：/home/支付服务/springboot/a",
            "SpringBoot项目包路径：/home/支付服务/springboot/b",
            "SpringBoot项目包路径：/home/订单服务/springboot/c",
            "SpringBoot子包名称：pay.jar",
            "SpringBoot子包名称：pay.jar",
            "SpringBoot子包名称：order.jar",
        ]
    )
    pairs, ok = parse_plugin_output_pairs(text)
    assert ok is True
    assert ("支付服务", "pay.jar") in pairs
    assert ("订单服务", "order.jar") in pairs


def test_end_to_end_excel(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["插件输出", "ID编号", "IP/域名", "漏洞标题", "工单漏洞等级", "关联资产"])
    ws.append(
        [
            "SpringBoot项目包路径：/home/支付服务/springboot/x\nSpringBoot子包名称：pay.jar\nSpringBoot子包名称：pay2.jar",
            "127017",
            "10.1.1.1",
            "Tomcat 遍历漏洞",
            "高危",
            "资产服务A",
        ]
    )
    ws.append(["完全不包含关键字", "127018", "10.1.1.2", "其他漏洞", "低危", ""])
    input_xlsx = tmp_path / "in.xlsx"
    wb.save(input_xlsx)

    config = AppConfig(
        columns=ColumnMapping(
            plugin_output="插件输出",
            id="ID编号",
            ip_or_domain="IP/域名",
            title="漏洞标题",
            severity="工单漏洞等级",
            related_asset="关联资产",
        ),
        high_levels=("高危", "超危"),
        systems=(SystemConfig(name="系统A", ips=("10.1.1.1", "10.1.1.2")),),
        iap_titles=("Tomcat 遍历漏洞",),
        iap_subpackage_patterns=("tomcat-embed-core-*.jar",),
    )

    rows, _ = read_vuln_records_from_excel(input_xlsx, config.columns, sheet_name=None)
    records = build_records(rows, config)

    assert records[0].system == "系统A"
    assert records[0].iap_category == "IAP"
    assert records[0].service_name == "资产服务A"
    assert any(r.service_name == "其他" for r in records)

    system_summary = summarize_by_system(records, config.high_levels)
    assert system_summary[0]["总漏洞"] == 2
    assert system_summary[0]["IAP漏洞数"] == 1
    assert system_summary[0]["非IAP漏洞数"] == 1
    assert system_summary[0]["高危以上"] == 1
    assert system_summary[0]["高危以上IAP"] == 1
    assert system_summary[0]["漏洞种类数(标题去重)"] == 2

    system_service_summary = summarize_by_system_service(records, config.high_levels)
    keys = {(r["系统"], r["服务名"]) for r in system_service_summary}
    assert ("系统A", "资产服务A") in keys
    assert ("系统A", "其他") in keys
    row_pay = next(r for r in system_service_summary if r["系统"] == "系统A" and r["服务名"] == "资产服务A")
    assert row_pay["总漏洞"] == 1
    assert row_pay["IAP总漏洞"] == 1
    assert row_pay["高危以上IAP总漏洞"] == 1

    system_iap_service_subpackage_summary = summarize_by_system_iap_service_subpackage(records, config.high_levels)
    keys2 = {(r["系统"], r["服务名"], r["子包名称"]) for r in system_iap_service_subpackage_summary}
    assert ("系统A", "资产服务A", "pay.jar") in keys2
    assert ("系统A", "资产服务A", "pay2.jar") in keys2
    row_payjar = next(
        r
        for r in system_iap_service_subpackage_summary
        if r["系统"] == "系统A" and r["服务名"] == "资产服务A" and r["子包名称"] == "pay.jar"
    )
    assert "127017" in (row_payjar["漏洞Id汇总"] or "")
    assert "Tomcat 遍历漏洞" in (row_payjar["漏洞标题汇总"] or "")


def test_iap_match_by_subpackage_pattern_when_title_not_found(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["插件输出", "ID编号", "IP/域名", "漏洞标题", "工单漏洞等级", "关联资产"])
    ws.append(
        [
            "SpringBoot项目包路径：/home/任意服务/springboot/x\nSpringBoot子包名称：tomcat-embed-core-9.0.14.jar",
            "200001",
            "10.1.1.1",
            "完全无关标题",
            "高危",
            "",
        ]
    )
    input_xlsx = tmp_path / "in2.xlsx"
    wb.save(input_xlsx)

    config = AppConfig(
        columns=ColumnMapping(
            plugin_output="插件输出",
            id="ID编号",
            ip_or_domain="IP/域名",
            title="漏洞标题",
            severity="工单漏洞等级",
            related_asset="关联资产",
        ),
        high_levels=("高危", "超危"),
        systems=(SystemConfig(name="系统A", ips=("10.1.1.1",)),),
        iap_titles=(),
        iap_subpackage_patterns=("tomcat-embed-core-*.jar",),
    )

    rows, _ = read_vuln_records_from_excel(input_xlsx, config.columns, sheet_name=None)
    records = build_records(rows, config)
    assert records[0].iap_category == "IAP"
