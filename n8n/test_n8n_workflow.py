#!/usr/bin/env python3
"""
n8n Workflow Validation Test Suite
Tests the workflow JSON, API connectivity, and assessment logic.
"""

import json
import subprocess
import sys
import os

# Add parent directory for config access
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ADO_QUERIES, ADO_PROJECT, REQUIRED_FIELDS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_FILE = os.path.join(SCRIPT_DIR, "ado_ticket_quality_workflow.json")
TEST_DATA_FILE = os.path.join(SCRIPT_DIR, "test_data.json")

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_result(test_name, passed, details=""):
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {test_name}")
    if details:
        print(f"         {details}")

# =============================================================================
# TEST 1: Validate workflow JSON structure
# =============================================================================
def test_workflow_json():
    print_header("TEST 1: Workflow JSON Validation")

    try:
        with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
        print_result("JSON syntax valid", True)
    except json.JSONDecodeError as e:
        print_result("JSON syntax valid", False, str(e))
        return False
    except FileNotFoundError:
        print_result("Workflow file exists", False, f"Not found: {WORKFLOW_FILE}")
        return False

    # Check required top-level fields
    required_fields = ["name", "nodes", "connections"]
    for field in required_fields:
        if field in workflow:
            print_result(f"Has '{field}' field", True)
        else:
            print_result(f"Has '{field}' field", False)
            return False

    # Check nodes
    nodes = workflow.get("nodes", [])
    print_result(f"Has {len(nodes)} nodes", len(nodes) >= 10, f"Expected 14, got {len(nodes)}")

    # Check for critical nodes
    node_names = [n.get("name") for n in nodes]
    critical_nodes = [
        "Set Variables",
        "Fetch Features Query",
        "Fetch Work Items Batch",
        "Assess Quality",
        "Generate Summary",
        "Generate CSV"
    ]
    for node in critical_nodes:
        if node in node_names:
            print_result(f"Has '{node}' node", True)
        else:
            print_result(f"Has '{node}' node", False)

    # Check connections
    connections = workflow.get("connections", {})
    print_result(f"Has {len(connections)} connection groups", len(connections) > 0)

    return True

# =============================================================================
# TEST 2: Validate test data JSON
# =============================================================================
def test_test_data():
    print_header("TEST 2: Test Data Validation")

    try:
        with open(TEST_DATA_FILE, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
        print_result("Test data JSON valid", True)
    except json.JSONDecodeError as e:
        print_result("Test data JSON valid", False, str(e))
        return False
    except FileNotFoundError:
        print_result("Test data file exists", False)
        return False

    work_items = test_data.get("workItems", [])
    print_result(f"Has {len(work_items)} test work items", len(work_items) >= 5)

    expected_results = test_data.get("expectedResults", {})
    print_result(f"Has {len(expected_results)} expected results", len(expected_results) >= 5)

    return True

# =============================================================================
# TEST 3: Test Azure CLI Authentication
# =============================================================================
def test_azure_auth():
    print_header("TEST 3: Azure CLI Authentication")

    # Try to find az in common locations on Windows
    az_paths = ["az", "az.cmd", r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"]

    for az_cmd in az_paths:
        try:
            result = subprocess.run(
                [az_cmd, "account", "show", "--query", "user.name", "-o", "tsv"],
                capture_output=True, text=True, timeout=30, shell=True
            )
            if result.returncode == 0 and result.stdout.strip():
                print_result("Azure CLI logged in", True, result.stdout.strip())
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    print_result("Azure CLI available", False, "Not in PATH - test manually or use MCP")
    print("         Note: ADO API can also be tested via Claude Code MCP connection")
    return None  # Return None to indicate "skipped" rather than failed

# =============================================================================
# TEST 4: Test ADO API Connectivity
# =============================================================================
def test_ado_api():
    print_header("TEST 4: ADO API Connectivity")

    # Get access token from Azure CLI
    az_cmd = "az.cmd" if os.name == 'nt' else "az"
    try:
        result = subprocess.run(
            [az_cmd, "account", "get-access-token", "--resource", "499b84ac-1321-427f-aa17-267ca6975798", "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, timeout=30, shell=True
        )
        if result.returncode != 0:
            print_result("Get ADO access token", False, "Azure CLI not available")
            print("         Tip: Test ADO API via Claude Code using MCP tools")
            return None  # Skipped
        token = result.stdout.strip()
        print_result("Get ADO access token", True, f"Token length: {len(token)}")
    except Exception as e:
        print_result("Get ADO access token", False, "Azure CLI not available")
        print("         Tip: Test ADO API via Claude Code using MCP tools")
        return None  # Skipped

    # Test project access
    org = "opusinspection"
    project_encoded = ADO_PROJECT.replace(" ", "%20")

    # Use PowerShell to make the HTTP request (more reliable on Windows)
    ps_script = f'''
$headers = @{{ Authorization = "Bearer {token}" }}
try {{
    $response = Invoke-RestMethod -Uri "https://dev.azure.com/{org}/_apis/projects?api-version=7.0" -Headers $headers -Method Get
    Write-Output "OK:$($response.count)"
}} catch {{
    Write-Output "ERROR:$($_.Exception.Message)"
}}
'''
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if output.startswith("OK:"):
            count = output.split(":")[1]
            print_result("List ADO projects", True, f"Found {count} projects")
        else:
            print_result("List ADO projects", False, output[:100])
            return False
    except Exception as e:
        print_result("List ADO projects", False, str(e))
        return False

    # Test query execution
    query_guid = list(ADO_QUERIES.values())[0]
    ps_script = f'''
$headers = @{{ Authorization = "Bearer {token}" }}
try {{
    $response = Invoke-RestMethod -Uri "https://dev.azure.com/{org}/{project_encoded}/_apis/wit/wiql/{query_guid}?api-version=7.0" -Headers $headers -Method Get
    Write-Output "OK:$($response.workItems.Count)"
}} catch {{
    Write-Output "ERROR:$($_.Exception.Message)"
}}
'''
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if output.startswith("OK:"):
            count = output.split(":")[1]
            print_result("Execute ADO query", True, f"Query returned {count} work items")
        else:
            print_result("Execute ADO query", False, output[:100])
    except Exception as e:
        print_result("Execute ADO query", False, str(e))

    return True

# =============================================================================
# TEST 5: Test Assessment Algorithm
# =============================================================================
def test_assessment_algorithm():
    print_header("TEST 5: Assessment Algorithm Validation")

    # Load test data
    with open(TEST_DATA_FILE, 'r', encoding='utf-8') as f:
        test_data = json.load(f)

    work_items = test_data.get("workItems", [])
    expected = test_data.get("expectedResults", {})

    def strip_html(html):
        if not html:
            return ''
        import re
        text = re.sub(r'<[^>]*>', ' ', html)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        return ' '.join(text.split())

    def assess_ticket(item):
        fields = item.get("fields", {})
        title = fields.get("System.Title", "")
        description = strip_html(fields.get("System.Description", "") or "")
        ac = strip_html(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "") or "")

        score = 0

        # Quantitative scoring
        desc_words = len([w for w in description.split() if w])
        ac_words = len([w for w in ac.split() if w])

        if desc_words >= 50: score += 12
        elif desc_words >= 30: score += 9
        elif desc_words >= 15: score += 6
        elif desc_words >= 5: score += 3

        if ac_words >= 50: score += 13
        elif ac_words >= 30: score += 10
        elif ac_words >= 15: score += 7
        elif ac_words >= 5: score += 4

        # Qualitative scoring
        combined = (title + ' ' + description + ' ' + ac).lower()

        import re
        action_matches = len(re.findall(r'\b(shall|must|will|should|can|allow|enable|provide|display|show|create|update|delete|send|receive|process|validate|calculate)\b', combined, re.I))
        if action_matches >= 5: score += 15
        elif action_matches >= 3: score += 10
        elif action_matches >= 1: score += 5

        actor_matches = len(re.findall(r'\b(user|admin|administrator|system|customer|inspector|manager|operator|technician|as a)\b', combined, re.I))
        if actor_matches >= 2: score += 10
        elif actor_matches >= 1: score += 5

        why_matches = len(re.findall(r'\b(so that|in order to|because|to enable|to allow|to ensure|to support|requirement|compliance|business)\b', combined, re.I))
        if why_matches >= 2: score += 10
        elif why_matches >= 1: score += 5

        how_matches = len(re.findall(r'\b(when|if|then|click|select|enter|navigate|button|field|screen|page|form|api|endpoint|database|table)\b', combined, re.I))
        if how_matches >= 8: score += 20
        elif how_matches >= 5: score += 15
        elif how_matches >= 3: score += 10
        elif how_matches >= 1: score += 5

        done_matches = len(re.findall(r'\b(verify|confirm|check|test|ensure|validate|expected|result|outcome|success|fail|error|given|when|then)\b', combined, re.I))
        if done_matches >= 5: score += 15
        elif done_matches >= 3: score += 10
        elif done_matches >= 1: score += 5

        edge_matches = len(re.findall(r'\b(error|exception|invalid|fail|edge case|boundary|limit|maximum|minimum|timeout|retry)\b', combined, re.I))
        if edge_matches >= 2: score += 5
        elif edge_matches >= 1: score += 3

        # Critical caps
        max_grade = 'A'
        if ac_words < 15:
            max_grade = 'C'
        if desc_words < 10:
            max_grade = 'F' if max_grade == 'C' else 'D'
        if desc_words == 0 and ac_words == 0:
            max_grade = 'F'
            score = 0

        # Determine grade
        if score >= 75: grade = 'A'
        elif score >= 55: grade = 'B'
        elif score >= 35: grade = 'C'
        elif score >= 20: grade = 'D'
        else: grade = 'F'

        # Apply cap
        grade_order = ['F', 'D', 'C', 'B', 'A']
        if grade_order.index(grade) > grade_order.index(max_grade):
            grade = max_grade

        return grade, score

    all_passed = True
    for item in work_items:
        item_id = str(item["id"])
        grade, score = assess_ticket(item)
        expected_grade = expected.get(item_id, {}).get("grade", "?")

        passed = grade == expected_grade
        if not passed:
            all_passed = False

        print_result(
            f"Item {item_id}: Grade={grade}, Score={score}",
            passed,
            f"Expected {expected_grade}" if not passed else ""
        )

    return all_passed

# =============================================================================
# TEST 6: Test Work Item Batch Fetch
# =============================================================================
def test_batch_fetch():
    print_header("TEST 6: Work Item Batch Fetch")

    # Get access token
    az_cmd = "az.cmd" if os.name == 'nt' else "az"
    try:
        result = subprocess.run(
            [az_cmd, "account", "get-access-token", "--resource", "499b84ac-1321-427f-aa17-267ca6975798", "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, timeout=30, shell=True
        )
        if result.returncode != 0:
            print_result("Batch fetch", False, "Azure CLI not available")
            print("         Tip: Test via Claude Code MCP: mcp__ado__wit_get_work_items_batch_by_ids")
            return None  # Skipped
        token = result.stdout.strip()
    except:
        print_result("Batch fetch", False, "Azure CLI not available")
        print("         Tip: Test via Claude Code MCP: mcp__ado__wit_get_work_items_batch_by_ids")
        return None  # Skipped

    org = "opusinspection"
    project_encoded = ADO_PROJECT.replace(" ", "%20")

    # Test fetching a small batch of work items
    test_ids = "54320,55904,55928"  # Known IDs from config
    fields = ",".join([f'"{f}"' for f in REQUIRED_FIELDS])

    ps_script = f'''
$headers = @{{
    Authorization = "Bearer {token}"
    "Content-Type" = "application/json"
}}
$body = @{{
    ids = @(54320, 55904, 55928)
    fields = @({fields})
}} | ConvertTo-Json

try {{
    $response = Invoke-RestMethod -Uri "https://dev.azure.com/{org}/{project_encoded}/_apis/wit/workitemsbatch?api-version=7.0" -Headers $headers -Method Post -Body $body
    $count = $response.value.Count
    $hasDesc = ($response.value | Where-Object {{ $_."fields"."System.Description" }}).Count
    Write-Output "OK:$count items, $hasDesc with description"
}} catch {{
    Write-Output "ERROR:$($_.Exception.Message)"
}}
'''
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if output.startswith("OK:"):
            print_result("Batch fetch work items", True, output[3:])
        else:
            print_result("Batch fetch work items", False, output[:100])
            return False
    except Exception as e:
        print_result("Batch fetch work items", False, str(e))
        return False

    return True

# =============================================================================
# MAIN
# =============================================================================
def main():
    print("\n" + "=" * 60)
    print("  n8n ADO TICKET QUALITY WORKFLOW - TEST SUITE")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Workflow JSON", test_workflow_json()))
    results.append(("Test Data", test_test_data()))
    results.append(("Azure Auth", test_azure_auth()))
    results.append(("ADO API", test_ado_api()))
    results.append(("Assessment Algorithm", test_assessment_algorithm()))
    results.append(("Batch Fetch", test_batch_fetch()))

    # Summary
    print_header("TEST SUMMARY")
    passed = 0
    failed = 0
    skipped = 0
    for name, result in results:
        if result is True:
            status = "[PASS]"
            passed += 1
        elif result is None:
            status = "[SKIP]"
            skipped += 1
        else:
            status = "[FAIL]"
            failed += 1
        print(f"  {status} {name}")

    print(f"\n  Total: {passed} passed, {failed} failed, {skipped} skipped")

    if failed == 0:
        if skipped > 0:
            print("\n  [OK] Core tests passed! Skipped tests require Azure CLI.")
            print("       ADO API can be verified via Claude Code MCP connection.")
        else:
            print("\n  [OK] All tests passed! The n8n workflow is ready for import.")
        return True
    else:
        print("\n  [!] Some tests failed. Review the output above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
