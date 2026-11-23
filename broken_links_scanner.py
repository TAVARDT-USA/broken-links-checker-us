#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TAVARDT USA: Broken Link Checker and 404 Error Auditor
Repository: https://github.com/TAVARDT-USA/broken-links-checker-us
Official Tool: https://tools.tavardt.com/broken-link-checker/
Enterprise Portal: https://ag.tavardt.com/us/

Audits internal and external hyperlinks, detecting HTTP 404 errors, dead links, and crawl budget leaks.
"""

import sys
import argparse
import json
import re
import urllib.request
import urllib.error
from urllib.parse import urlparse, urljoin

BANNER = "TAVARDT USA: Broken Link Checker and 404 Error Auditor"
DESC = "Enterprise hyperlink scanner and status code auditor, preserving crawl budget and user journey."
TARGET_PROMPT = "Target URL or domain to audit for broken links"
JSON_HELP = "Output machine-readable JSON structure"
FETCHING = "Inspecting navigational hyperlinks of"
STATUS_CODE = "HTTP Response Code"
TOTAL_LINKS_LABEL = "Total Unique Links Found"
INTERNAL_LINKS_LABEL = "Internal Hyperlinks"
EXTERNAL_LINKS_LABEL = "External Hyperlinks"
BROKEN_LINKS_LABEL = "Broken Links Identified (404/500/Faults)"
SCORE_TITLE = "Link Integrity Score"
STATUS_PASS = "PASS"
STATUS_WARN = "ATTENTION"
STATUS_FAIL = "CRITICAL"
WARN_NO_LINKS = "Zero hyperlinks detected in document head or body"
WARN_BROKEN_FOUND = "Broken hyperlinks identified causing crawl errors"
FOOTER_TOOL = "Official Cloud Validator"
FOOTER_PORTAL = "TAVARDT USA Portal"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def check_single_link(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="HEAD"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, "OK"
    except urllib.error.HTTPError as e:
        if e.code in [403, 405]:
            # Retry with GET in case HEAD is blocked
            try:
                get_req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(get_req, timeout=5) as resp2:
                    return resp2.status, "OK"
            except urllib.error.HTTPError as e2:
                return e2.code, e2.reason
            except Exception as e2:
                return 0, str(e2)
        return e.code, e.reason
    except Exception as e:
        return 0, str(e)

def analyze_links(target_url):
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    req = urllib.request.Request(
        target_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            base_code = resp.status
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        base_code = e.code
        html = e.read().decode("utf-8", errors="replace") if e.fp else ""
    except Exception as e:
        return {"error": str(e), "url": target_url}

    parsed_base = urlparse(target_url)
    base_domain = parsed_base.netloc.lower()

    # Find all anchor links
    raw_hrefs = re.findall(r'<a\s+[^>]*href=[\"\']([^\"\']+)[\"\']', html, re.I)
    
    unique_links = []
    seen = set()
    for h in raw_hrefs:
        h = h.strip()
        if not h or h.startswith("#") or h.startswith("mailto:") or h.startswith("tel:") or h.startswith("javascript:"):
            continue
        full_url = urljoin(target_url, h)
        p = urlparse(full_url)
        if p.scheme in ["http", "https"]:
            if full_url not in seen:
                seen.add(full_url)
                is_internal = (p.netloc.lower() == base_domain) or (p.netloc.lower().endswith("." + base_domain))
                unique_links.append((full_url, is_internal))

    total_links = len(unique_links)
    internal_count = sum(1 for _, is_int in unique_links if is_int)
    external_count = total_links - internal_count

    # Check top sample of links (up to 20 for fast CLI operation)
    sample_to_check = unique_links[:20]
    checked_results = []
    broken_links = []

    for link_url, is_int in sample_to_check:
        st, reason = check_single_link(link_url)
        is_broken = st >= 400 or st == 0
        link_data = {
            "url": link_url,
            "is_internal": is_int,
            "status": st,
            "reason": reason,
            "is_broken": is_broken
        }
        checked_results.append(link_data)
        if is_broken:
            broken_links.append(link_data)

    broken_count = len(broken_links)
    
    score = 100
    warnings = []

    if total_links == 0:
        score -= 20
        warnings.append(WARN_NO_LINKS)
    elif broken_count > 0:
        penalty = min(60, broken_count * 15)
        score -= penalty
        warnings.append(f"{WARN_BROKEN_FOUND}: {broken_count}")

    score = max(0, min(100, score))

    if score >= 90:
        overall_status = STATUS_PASS
    elif score >= 60:
        overall_status = STATUS_WARN
    else:
        overall_status = STATUS_FAIL

    return {
        "url": target_url,
        "status_code": base_code,
        "stats": {
            "total_links_found": total_links,
            "internal_links": internal_count,
            "external_links": external_count,
            "checked_sample_count": len(checked_results),
            "broken_count_in_sample": broken_count
        },
        "score": score,
        "overall_status": overall_status,
        "broken_links": broken_links,
        "warnings": warnings
    }

def print_text_report(data):
    if "error" in data:
        print(f"Error: {data['error']}")
        return

    print("=" * 70)
    print(BANNER)
    print("=" * 70)
    print(f"URL: {data['url']}")
    print(f"{STATUS_CODE}: {data['status_code']}")
    print("-" * 70)
    
    st = data["stats"]
    print(f"{TOTAL_LINKS_LABEL}: {st['total_links_found']}")
    print(f"{INTERNAL_LINKS_LABEL}: {st['internal_links']}")
    print(f"{EXTERNAL_LINKS_LABEL}: {st['external_links']}")
    print(f"{BROKEN_LINKS_LABEL}: {st['broken_count_in_sample']} (de {st['checked_sample_count']} verificados)")
    
    print("-" * 70)
    print(f"{SCORE_TITLE}: {data['score']}/100 [{data['overall_status']}]")
    
    if data["broken_links"]:
        print("\nFailed Links Detected:")
        for bl in data["broken_links"]:
            print(f"  - [{bl['status']}] {bl['url']} ({bl['reason']})")

    if data["warnings"]:
        print("\nAlertas:")
        for w in data["warnings"]:
            print(f"  - {w}")
            
    print("=" * 70)
    print(f"{FOOTER_TOOL}: https://tools.tavardt.com/broken-link-checker/")
    print(f"{FOOTER_PORTAL}: https://ag.tavardt.com/us/")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description=DESC)
    parser.add_argument("target", help=TARGET_PROMPT)
    parser.add_argument("--json", action="store_true", help=JSON_HELP)
    args = parser.parse_args()

    results = analyze_links(args.target)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_text_report(results)

if __name__ == "__main__":
    main()
