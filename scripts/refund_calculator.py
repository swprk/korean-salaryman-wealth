#!/usr/bin/env python3
"""
한국 직장인 절세계좌 환급 계산기

사용법:
    python refund_calculator.py --salary 5000 --pension 600 --irp 300 --isa-transfer 0
    python refund_calculator.py --gain 1200  # 해외주식 양도세 계산
    python refund_calculator.py --interactive  # 대화형 모드

기능:
1. 연금저축·IRP·ISA이전 환급액 계산 (16.5% / 13.2% 자동 분기)
2. 해외주식 양도소득세 계산 (250만원 공제 + 22%)
3. 손익통산·연말연초 분할 매도 절세 시뮬레이션
4. 종합 시나리오 비교 (보수/표준/공격)

2026년 4월 기준. 세제 변경 시 RATES 상수만 수정하면 됨.
"""

import argparse
import sys

# 2026년 4월 기준 세제 상수
RATES = {
    # 연금계좌 세액공제
    "tax_credit_low": 0.165,    # 연봉 5,500만원 이하
    "tax_credit_high": 0.132,   # 연봉 5,500만원 초과
    "salary_threshold": 5500,   # 만원 단위

    # 연금계좌 한도
    "pension_limit": 600,       # 연금저축 단독 한도
    "pension_irp_limit": 900,   # 연금저축 + IRP 합산 한도
    "isa_transfer_extra": 300,  # ISA→연금이전 추가 한도

    # ISA
    "isa_annual_limit": 2000,
    "isa_total_limit": 10000,   # 5년 1억
    "isa_tax_free_general": 200,    # 일반형 비과세 한도
    "isa_tax_free_low_income": 400, # 서민형 비과세 한도
    "isa_separate_tax": 0.099,  # 분리과세율 9.9%
    "isa_low_income_salary": 5000,  # 서민형 자격 (총급여 만원)

    # 해외주식 양도소득세
    "capital_gains_tax": 0.22,  # 22% (국세 20% + 지방세 2%)
    "capital_gains_deduction": 250,  # 250만원 공제

    # 일반계좌 배당·이자세
    "dividend_tax": 0.154,  # 15.4%

    # 종합과세
    "comprehensive_threshold": 2000,  # 금융소득 종합과세 진입 임계점
}


def get_credit_rate(salary_man_won: int) -> float:
    """연봉(만원)에 따른 세액공제율 반환"""
    return RATES["tax_credit_low"] if salary_man_won <= RATES["salary_threshold"] else RATES["tax_credit_high"]


def calc_pension_refund(
    salary: int,
    pension: int = 0,
    irp: int = 0,
    isa_transfer: int = 0,
) -> dict:
    """
    연금계좌 + ISA이전 환급액 계산

    Args:
        salary: 연봉 (만원)
        pension: 연금저축 납입액 (만원)
        irp: IRP 추가 납입액 (만원)
        isa_transfer: ISA 만기 후 연금이전 금액 (만원)

    Returns:
        dict: 각 항목별 환급액과 합계
    """
    rate = get_credit_rate(salary)

    # 연금저축 한도 적용
    pension_eligible = min(pension, RATES["pension_limit"])

    # IRP 한도 (연금저축과 합산 900만원)
    combined_limit = RATES["pension_irp_limit"] - pension_eligible
    irp_eligible = min(irp, combined_limit)

    # ISA 이전 추가 한도
    isa_transfer_eligible = min(isa_transfer, RATES["isa_transfer_extra"])

    pension_refund = pension_eligible * rate
    irp_refund = irp_eligible * rate
    isa_transfer_refund = isa_transfer_eligible * rate
    total = pension_refund + irp_refund + isa_transfer_refund

    return {
        "salary": salary,
        "rate": rate,
        "rate_pct": f"{rate * 100:.1f}%",
        "pension": {"input": pension, "eligible": pension_eligible, "refund": pension_refund},
        "irp": {"input": irp, "eligible": irp_eligible, "refund": irp_refund},
        "isa_transfer": {"input": isa_transfer, "eligible": isa_transfer_eligible, "refund": isa_transfer_refund},
        "total_refund": total,
        "total_eligible": pension_eligible + irp_eligible + isa_transfer_eligible,
        "warnings": _check_warnings(pension, irp, isa_transfer),
    }


def _check_warnings(pension: int, irp: int, isa_transfer: int) -> list:
    """입력값 경고 메시지 생성"""
    warnings = []
    if pension > RATES["pension_limit"]:
        warnings.append(
            f"연금저축 {pension}만원 → {RATES['pension_limit']}만원 한도 초과분 "
            f"({pension - RATES['pension_limit']}만원)은 세액공제 대상 아님"
        )
    combined = pension + irp
    if combined > RATES["pension_irp_limit"]:
        warnings.append(
            f"연금저축+IRP 합산 {combined}만원 → {RATES['pension_irp_limit']}만원 한도 초과"
        )
    if isa_transfer > RATES["isa_transfer_extra"]:
        warnings.append(
            f"ISA이전 {isa_transfer}만원 → {RATES['isa_transfer_extra']}만원 한도 초과"
        )
    return warnings


def calc_capital_gains_tax(gain: int, cost_deduction: int = 0) -> dict:
    """
    해외주식 양도소득세 계산

    Args:
        gain: 양도차익 (만원)
        cost_deduction: 필요경비 차감액 (만원, 매매수수료 등)

    Returns:
        dict: 과세표준, 세액, 절세 여지
    """
    net_gain = gain - cost_deduction
    deduction = RATES["capital_gains_deduction"]
    taxable = max(0, net_gain - deduction)
    tax = taxable * RATES["capital_gains_tax"]

    # 분할 매도 절세 시뮬레이션
    half_year_split_savings = 0
    if net_gain > deduction * 2:
        # 12월/1월 분할 시 250만원 두 번 공제 가능
        # 단, 같은 해 차익이 이미 발생한 경우엔 적용 어려움 → 미래 매도 가정
        future_taxable_no_split = max(0, net_gain - deduction)
        future_taxable_with_split = max(0, net_gain - deduction * 2)
        half_year_split_savings = (future_taxable_no_split - future_taxable_with_split) * RATES["capital_gains_tax"]

    return {
        "gain": gain,
        "cost_deduction": cost_deduction,
        "net_gain": net_gain,
        "deduction": deduction,
        "taxable": taxable,
        "tax_rate_pct": f"{RATES['capital_gains_tax'] * 100:.0f}%",
        "tax": tax,
        "post_tax_amount": net_gain - tax,
        "split_savings_potential": half_year_split_savings,
        "filing_period": "다음 해 5월 1일~31일 홈택스 자진신고",
    }


def calc_isa_vs_general_account(annual_gain: int, salary: int) -> dict:
    """
    ISA vs 일반 위탁계좌 세후 수익 비교

    Args:
        annual_gain: 연간 차익 (만원)
        salary: 연봉 (만원, 서민형 ISA 자격 판단용)

    Returns:
        dict: 두 계좌의 세후 수익 비교
    """
    # ISA (서민형 자격 자동 판단)
    is_low_income = salary <= RATES["isa_low_income_salary"]
    isa_tax_free = RATES["isa_tax_free_low_income"] if is_low_income else RATES["isa_tax_free_general"]
    isa_taxable = max(0, annual_gain - isa_tax_free)
    isa_tax = isa_taxable * RATES["isa_separate_tax"]
    isa_post_tax = annual_gain - isa_tax

    # 일반 위탁계좌 (배당세 15.4% 가정 — 국내상장 해외 ETF의 경우)
    general_tax = annual_gain * RATES["dividend_tax"]
    general_post_tax = annual_gain - general_tax

    # 일반 위탁계좌 (양도세 22% 가정 — 직상장 해외 ETF의 경우)
    overseas_taxable = max(0, annual_gain - RATES["capital_gains_deduction"])
    overseas_tax = overseas_taxable * RATES["capital_gains_tax"]
    overseas_post_tax = annual_gain - overseas_tax

    return {
        "annual_gain": annual_gain,
        "is_low_income_isa": is_low_income,
        "isa_tax_free_limit": isa_tax_free,
        "isa": {"tax": isa_tax, "post_tax": isa_post_tax},
        "general_dividend_15_4": {"tax": general_tax, "post_tax": general_post_tax},
        "overseas_capital_gains_22": {"tax": overseas_tax, "post_tax": overseas_post_tax},
        "best_choice": _find_best_choice(isa_post_tax, general_post_tax, overseas_post_tax),
    }


def _find_best_choice(isa: float, general: float, overseas: float) -> str:
    """세 가지 중 최적 계좌 선택"""
    options = {"ISA": isa, "일반계좌(국내상장 해외ETF)": general, "일반계좌(직상장 해외ETF)": overseas}
    best = max(options, key=options.get)
    return f"{best} (세후 {options[best]:.1f}만원)"


# ======== 출력 포맷 ========

def print_pension_result(result: dict) -> None:
    """연금계좌 환급 결과 출력"""
    print("\n" + "=" * 60)
    print("📊 연금계좌 환급액 계산 결과")
    print("=" * 60)
    print(f"연봉: {result['salary']:,}만원 → 세액공제율 {result['rate_pct']}")
    print()
    print(f"{'항목':<25}{'납입':>10}{'한도내':>10}{'환급':>10}")
    print("-" * 60)

    p = result["pension"]
    print(f"{'연금저축':<25}{p['input']:>9,}만{p['eligible']:>9,}만{p['refund']:>9.1f}만")

    i = result["irp"]
    print(f"{'IRP 추가':<25}{i['input']:>9,}만{i['eligible']:>9,}만{i['refund']:>9.1f}만")

    isa = result["isa_transfer"]
    print(f"{'ISA→연금이전':<25}{isa['input']:>9,}만{isa['eligible']:>9,}만{isa['refund']:>9.1f}만")

    print("-" * 60)
    print(f"{'합계':<25}{'':<10}{result['total_eligible']:>9,}만{result['total_refund']:>9.1f}만")
    print()
    print(f"💰 총 환급액: {result['total_refund']:.1f}만원")

    if result["warnings"]:
        print("\n⚠️  경고:")
        for w in result["warnings"]:
            print(f"   - {w}")

    print("\n💡 다음 단계:")
    if result["total_eligible"] < RATES["pension_irp_limit"]:
        remaining = RATES["pension_irp_limit"] - result["total_eligible"]
        print(f"   - 연금계좌 추가 {remaining}만원 납입 시 추가 환급 {remaining * result['rate']:.1f}만원")
    if result["isa_transfer"]["input"] == 0:
        print(f"   - ISA 만기 후 연금이전 시 추가 한도 {RATES['isa_transfer_extra']}만원 활용 가능 (추가 환급 최대 {RATES['isa_transfer_extra'] * result['rate']:.1f}만원)")


def print_capital_gains_result(result: dict) -> None:
    """양도세 계산 결과 출력"""
    print("\n" + "=" * 60)
    print("📊 해외주식 양도소득세 계산 결과")
    print("=" * 60)
    print(f"양도차익: {result['gain']:,}만원")
    if result["cost_deduction"]:
        print(f"필요경비: {result['cost_deduction']:,}만원")
        print(f"순 양도차익: {result['net_gain']:,}만원")
    print(f"기본공제: {result['deduction']:,}만원")
    print(f"과세표준: {result['taxable']:,}만원")
    print(f"세율: {result['tax_rate_pct']} (국세 20% + 지방세 2%)")
    print()
    print(f"💸 납부세액: {result['tax']:.1f}만원")
    print(f"💰 세후 수익: {result['post_tax_amount']:.1f}만원")
    print(f"📅 신고: {result['filing_period']}")

    if result["split_savings_potential"] > 0:
        print(f"\n💡 절세 팁: 12월/1월 분할 매도로 250만원 공제 두 번 활용")
        print(f"   추가 절세 가능액: 최대 {result['split_savings_potential']:.1f}만원")


def print_account_comparison(result: dict) -> None:
    """ISA vs 일반계좌 비교 출력"""
    print("\n" + "=" * 60)
    print("📊 ISA vs 일반계좌 세후 수익 비교")
    print("=" * 60)
    print(f"연간 차익: {result['annual_gain']:,}만원")
    print(f"서민형 ISA 자격: {'✅ 가능' if result['is_low_income_isa'] else '❌ 일반형'}")
    print(f"ISA 비과세 한도: {result['isa_tax_free_limit']}만원")
    print()
    print(f"{'계좌 유형':<35}{'세금':>10}{'세후 수익':>12}")
    print("-" * 60)
    print(f"{'ISA (분리과세 9.9%)':<35}{result['isa']['tax']:>9.1f}만{result['isa']['post_tax']:>11.1f}만")
    print(f"{'일반계좌 (배당세 15.4%)':<35}{result['general_dividend_15_4']['tax']:>9.1f}만{result['general_dividend_15_4']['post_tax']:>11.1f}만")
    print(f"{'일반계좌 (양도세 22%)':<35}{result['overseas_capital_gains_22']['tax']:>9.1f}만{result['overseas_capital_gains_22']['post_tax']:>11.1f}만")
    print("-" * 60)
    print(f"\n🏆 최적: {result['best_choice']}")


# ======== 대화형 모드 ========

def interactive_mode() -> None:
    """대화형 입력 모드"""
    print("=" * 60)
    print("한국 직장인 절세계좌 환급 계산기 (2026년 기준)")
    print("=" * 60)
    print("\n원하는 계산을 선택하세요:")
    print("  1. 연금계좌 환급액 (연금저축·IRP·ISA이전)")
    print("  2. 해외주식 양도소득세")
    print("  3. ISA vs 일반계좌 세후 수익 비교")
    print("  4. 모두 (종합 시나리오)")

    choice = input("\n선택 [1-4]: ").strip()

    if choice in ("1", "4"):
        print("\n--- 연금계좌 입력 ---")
        salary = int(input("연봉 (만원): "))
        pension = int(input("연금저축 납입액 (만원, 없으면 0): ") or 0)
        irp = int(input("IRP 추가 납입액 (만원, 없으면 0): ") or 0)
        isa_transfer = int(input("ISA 만기 후 연금이전 (만원, 없으면 0): ") or 0)

        result = calc_pension_refund(salary, pension, irp, isa_transfer)
        print_pension_result(result)

    if choice in ("2", "4"):
        print("\n--- 해외주식 양도세 입력 ---")
        gain = int(input("연간 양도차익 (만원): "))
        cost = int(input("매매수수료 등 필요경비 (만원, 없으면 0): ") or 0)

        result = calc_capital_gains_tax(gain, cost)
        print_capital_gains_result(result)

    if choice in ("3", "4"):
        print("\n--- 계좌 비교 입력 ---")
        if "salary" not in dir():
            salary = int(input("연봉 (만원): "))
        annual = int(input("연간 차익 (만원): "))

        result = calc_isa_vs_general_account(annual, salary)
        print_account_comparison(result)

    print("\n" + "=" * 60)
    print("⚠️  본 계산은 2026년 4월 기준이며 세제 변경 시 결과가 달라집니다.")
    print("⚠️  복잡한 사안(증여, 종합과세 진입 등)은 세무사 상담을 권장합니다.")
    print("=" * 60)


# ======== CLI ========

def main():
    parser = argparse.ArgumentParser(
        description="한국 직장인 절세계좌 환급 계산기 (2026년 기준)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  연봉 5천 + 연금저축 600 + IRP 300:
    python refund_calculator.py --salary 5000 --pension 600 --irp 300

  해외주식 1,200만원 차익:
    python refund_calculator.py --gain 1200

  ISA vs 일반계좌 비교 (연봉 4,800, 연 차익 500):
    python refund_calculator.py --salary 4800 --compare 500

  대화형 모드:
    python refund_calculator.py --interactive
        """,
    )
    parser.add_argument("--salary", type=int, help="연봉 (만원)")
    parser.add_argument("--pension", type=int, default=0, help="연금저축 납입액 (만원)")
    parser.add_argument("--irp", type=int, default=0, help="IRP 추가 납입액 (만원)")
    parser.add_argument("--isa-transfer", type=int, default=0, help="ISA 만기 후 연금이전 (만원)")
    parser.add_argument("--gain", type=int, help="해외주식 연간 양도차익 (만원)")
    parser.add_argument("--cost", type=int, default=0, help="매매수수료 등 필요경비 (만원)")
    parser.add_argument("--compare", type=int, help="ISA vs 일반계좌 비교용 연간 차익 (만원)")
    parser.add_argument("--interactive", "-i", action="store_true", help="대화형 입력 모드")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    did_something = False

    if args.salary and (args.pension or args.irp or args.isa_transfer):
        result = calc_pension_refund(args.salary, args.pension, args.irp, args.isa_transfer)
        print_pension_result(result)
        did_something = True

    if args.gain is not None:
        result = calc_capital_gains_tax(args.gain, args.cost)
        print_capital_gains_result(result)
        did_something = True

    if args.compare is not None:
        if not args.salary:
            print("오류: --compare 사용 시 --salary 필수", file=sys.stderr)
            sys.exit(1)
        result = calc_isa_vs_general_account(args.compare, args.salary)
        print_account_comparison(result)
        did_something = True

    if not did_something:
        parser.print_help()
        print("\n💡 대화형 모드를 권장합니다: python refund_calculator.py -i")


if __name__ == "__main__":
    main()
