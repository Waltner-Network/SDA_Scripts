import re
import os
from collections import namedtuple

#set variables here

SITE = "MOT East"
DATE = "4.2"
active_folder= os.path.join(SITE,"Closed Mode", DATE)


InterfaceInfo = namedtuple("InterfaceInfo", ["status", "vlan"])
CDPNeighbor = namedtuple("CDPNeighbor", ["device_id", "local_intf", "port_id", "platform", "capability"])

DeviceTrackingEntry = namedtuple("DeviceTrackingEntry", ["code", "addr", "mac", "interface", "vlan", "prlvl", "age", "state", "time_left"])


# ---------- Helpers to extract command sections from a combined file ----------

def extract_command_block(text, command):
    """
    Extracts the text block for a given command from the full device output.
    Assumes the command line itself appears, e.g. 'show interface status'.
    Returns the text from the line after the command up to (but not including)
    the next line that starts with 'show ' or until EOF.
    """
    pattern = re.compile(rf"^.*{re.escape(command)}.*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""

    start = match.end()
    # Split the remaining text into lines
    remaining = text[start:]
    lines = remaining.splitlines()

    collected = []
    for line in lines:
        # crude heuristic: next show command = end of this block
        if re.match(r"^\S*#?\s*show\s+\S+", line):
            break
        collected.append(line)

    return "\n".join(collected).strip()


# ---------- Parsers ----------

def parse_show_interface_status(block):
    """
    Parse 'show interface status' output.
    Returns dict: {interface: InterfaceInfo(status, vlan)}
    """
    interfaces = {}

    if not block:
        return interfaces

    lines = block.splitlines()

    # Find header line first (the one containing 'Port' and 'Status' and 'Vlan')
    header_index = None
    for i, line in enumerate(lines):
        if ("Port" in line and "Status" in line and "Vlan" in line) or \
           ("Port" in line and "Status" in line and "VLAN" in line):
            header_index = i
            break

    if header_index is None:
        return interfaces

    # From the line after the header to the end, parse interfaces
    data_lines = lines[header_index + 1:]

    # Example line:
    # Gi1/0/1   name_here        connected    10     a-full  a-100 10/100/1000BaseTX
    intf_line_re = re.compile(
        r"^(?P<port>\S+)\s+"
        r"(?P<name>.*?)\s+"
        r"(?P<status>connected|notconnect|disabled|err-disabled|inactive|monitoring|suspended|up|down)\s+"
        r"(?P<vlan>\S+)",
        re.IGNORECASE,
    )

    for line in data_lines:
        line = line.rstrip()
        if not line.strip():
            continue
        m = intf_line_re.match(line)
        if not m:
            continue
        port = m.group("port")
        status = m.group("status")
        vlan = m.group("vlan")
        interfaces[port] = InterfaceInfo(status=status, vlan=vlan)

    return interfaces


def parse_show_cdp_neighbor(block):
    """
    Parse 'show cdp neighbor' output.
    Returns dict keyed by (local_intf, device_id) for uniqueness:
      {(local_intf, device_id): CDPNeighbor}
    """
    neighbors = {}

    if not block:
        return neighbors

    lines = block.splitlines()

    # Skip until header (one containing 'Device ID' and 'Local Intrfce')
    header_index = None
    for i, line in enumerate(lines):
        if "Device ID" in line and "Local Intrfce" in line:
            header_index = i
            break

    if header_index is None:
        return neighbors

    data_lines = lines[header_index + 1:]

    # Typical CDP line:
    # CORE01       Gi1/0/48          153        R S I       WS-C3850  Gi1/0/1
    # Device ID (no spaces in classic IOS) - but may use them; we'll treat first token as device id.
    cdp_re = re.compile(
        r"^(?P<device_id>\S+)\s+"
        r"(?P<local_intf>\S+\s*\S*)\s+"
        r"(?P<holdtme>\d+)\s+"
        r"(?P<capability>[\w ]+?)\s+"
        r"(?P<platform>\S+)\s+"
        r"(?P<port_id>.+)$"
    )

    for line in data_lines:
        line = line.rstrip()
        if not line.strip():
            continue
        m = cdp_re.match(line)
        if not m:
            continue

        device_id = m.group("device_id")
        local_intf = m.group("local_intf").strip()
        platform = m.group("platform")
        capability = m.group("capability").strip()
        port_id = m.group("port_id").strip()

        key = (local_intf, device_id)
        neighbors[key] = CDPNeighbor(
            device_id=device_id,
            local_intf=local_intf,
            port_id=port_id,
            platform=platform,
            capability=capability,
        )

    return neighbors



def parse_show_device_tracking_database(block):
    """
    Parse 'show device-tracking database' output (IOS-XE style).

    Example line:
    ARP 10.215.241.10                         0020.85d4.d603     Gi1/0/11   241   0005  152s   REACHABLE 151 s try 0

    Returns dict keyed by Network Layer Address (IPv4/IPv6) string:
        {addr: DeviceTrackingEntry(...)}
    """
    entries = {}

    if not block:
        return entries

    lines = block.splitlines()

    # Find header line containing 'Network Layer Address' and 'Link Layer Address'
    header_index = None
    for i, line in enumerate(lines):
        if "Network Layer Address" in line and "Link Layer Address" in line:
            header_index = i
            break

    if header_index is None:
        return entries

    data_lines = lines[header_index + 1:]

    # Regex based on your sample:
    # CODE  NLA                        MAC                INTf      VLAN  prlvl age    state     Time left...
    dt_re = re.compile(
        r"^(?P<code>\S+)\s+"
        r"(?P<addr>\S+)\s+"
        r"(?P<mac>[0-9a-fA-F\.:-]+)\s+"
        r"(?P<intf>\S+)\s+"
        r"(?P<vlan>\S+)\s+"
        r"(?P<prlvl>\S+)\s+"
        r"(?P<age>\S+)\s+"
        r"(?P<state>\S+)\s+"
        r"(?P<time_left>.+)$"
    )

    for line in data_lines:
        line = line.rstrip()
        if not line.strip():
            continue

        m = dt_re.match(line)
        if not m:
            # Skip non-data lines (e.g., blank or wrapping lines, if any)
            continue
        

        code = m.group("code")
        addr = m.group("addr")
        mac = m.group("mac")
        interface = m.group("intf")
        vlan = m.group("vlan")
        prlvl = m.group("prlvl")
        age = m.group("age")
        state = m.group("state")
        time_left = m.group("time_left").strip()

        if addr.lower().startswith("fe80"):
            #skip ipv6 link-local addresses as they are not relevant for our purposes and can be very noisy
            continue

        entries[addr] = DeviceTrackingEntry(
            code=code,
            addr=addr,
            mac=mac,
            interface=interface,
            vlan=vlan,
            prlvl=prlvl,
            age=age,
            state=state,
            time_left=time_left,
        )

    return entries

def parse_show_authentication_session(block):
    """
    Parse 'show authentication session' (table format).

    Returns dict keyed by (interface, mac):
    {
      ("Fi1/0/1", "0020.85e6.867c"): {
          "method": "mab",
          "domain": "DATA",
          "status": "Auth"
      }
    }
    """
    sessions = {}
    if not block:
        return sessions

    lines = block.splitlines()

    # Find header line
    header_index = None
    for i, line in enumerate(lines):
        if (
            "Interface" in line
            and "MAC Address" in line
            and "Method" in line
            and "Domain" in line
            and "Status" in line
        ):
            header_index = i
            break

    if header_index is None:
        return sessions

    data_lines = lines[header_index + 2 :]  # skip header + separator

    row_re = re.compile(
        r"^(?P<intf>\S+)\s+"
        r"(?P<mac>[0-9a-fA-F\.]+)\s+"
        r"(?P<method>\S+)\s+"
        r"(?P<domain>\S+)\s+"
        r"(?P<status>\S+)\s+"
        r"\S+\s+"           # Flags (ignored)
        r"\S+"              # Session ID (ignored)
    )

    for line in data_lines:
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("Session count"):
            break

        m = row_re.match(line)
        if not m:
            continue

        intf = m.group("intf")
        mac = m.group("mac")
        sessions[(intf, mac)] = {
            "method": m.group("method"),
            "domain": m.group("domain"),
            "status": m.group("status"),
        }

    return sessions


# ---------- Diff logic ----------

def diff_interfaces(before_intfs, after_intfs):
    """
    Compare interface status and VLAN.
    Returns dict with lists of changes.
    """
    status_changes = []
    vlan_changes = []
    only_in_before = []
    only_in_after = []

    before_ports = set(before_intfs.keys())
    after_ports = set(after_intfs.keys())

    for port in sorted(before_ports | after_ports):
        b = before_intfs.get(port)
        a = after_intfs.get(port)

        if b and not a:
            only_in_before.append(port)
        elif a and not b:
            only_in_after.append(port)
        else:
            # present in both
            if b.status != a.status:
                status_changes.append((port, b.status, a.status))
            if b.vlan != a.vlan:
                vlan_changes.append((port, b.vlan, a.vlan))

    return {
        "status_changes": status_changes,
        "vlan_changes": vlan_changes,
        "only_in_before": only_in_before,
        "only_in_after": only_in_after,
    }


def diff_cdp_neighbors(before_cdp, after_cdp):
    """
    Compare CDP neighbors.
    Returns dict with new, removed, and moved neighbors.
    """
    before_keys = set(before_cdp.keys())
    after_keys = set(after_cdp.keys())

    # For easier reasoning, also build mapping (device_id, port_id) -> local_intf
    def build_device_port_to_local(neighbors_dict):
        mapping = {}
        for (local_intf, device_id), n in neighbors_dict.items():
            mapping[(device_id, n.port_id)] = local_intf
        return mapping

    b_map = build_device_port_to_local(before_cdp)
    a_map = build_device_port_to_local(after_cdp)

    removed = []
    added = []
    moved = []

    # Check for removed and moved
    for (device_id, port_id), b_local in b_map.items():
        if (device_id, port_id) not in a_map:
            removed.append((device_id, port_id, b_local))
        else:
            a_local = a_map[(device_id, port_id)]
            if a_local != b_local:
                moved.append((device_id, port_id, b_local, a_local))

    # Check for added
    for (device_id, port_id), a_local in a_map.items():
        if (device_id, port_id) not in b_map:
            added.append((device_id, port_id, a_local))

    return {
        "removed": removed,
        "added": added,
        "moved": moved,
    }



def diff_device_tracking(before_dt, after_dt):
    """
    Compare device-tracking database.

    Keys by Network Layer Address (addr).
    Reports:
      - added: addrs only in AFTER
      - removed: addrs only in BEFORE
      - changed: same addr but code/mac/interface/vlan/state/prlvl changed
    """
    before_addrs = set(before_dt.keys())
    after_addrs = set(after_dt.keys())

    removed = sorted(before_addrs - after_addrs)
    added = sorted(after_addrs - before_addrs)
    changed = []

    for addr in sorted(before_addrs & after_addrs):
        b = before_dt[addr]
        a = after_dt[addr]

        diffs = {}
        if b.code != a.code:
            diffs["code"] = (b.code, a.code)
        if b.mac != a.mac:
            diffs["mac"] = (b.mac, a.mac)
        if b.interface != a.interface:
            diffs["interface"] = (b.interface, a.interface)
        if b.vlan != a.vlan:
            diffs["vlan"] = (b.vlan, a.vlan)
        if b.prlvl != a.prlvl:
            diffs["prlvl"] = (b.prlvl, a.prlvl)
        if b.state != a.state:
            diffs["state"] = (b.state, a.state)

        # age/time_left deliberately ignored to avoid noise

        if diffs:
            changed.append((addr, diffs))

    return {
        "removed": removed,
        "added": added,
        "changed": changed,
    }



# ---------- Main ----------

def post_check(before_file, after_file, output_file):

    with open(before_file, "r", encoding="utf-8", errors="ignore") as f:
        before_text = f.read()
    with open(after_file, "r", encoding="utf-8", errors="ignore") as f:
        after_text = f.read()

    # Extract relevant sections
    before_int_status_block = extract_command_block(before_text, "show interface status")
    after_int_status_block = extract_command_block(after_text, "show interface status")

    before_cdp_block = extract_command_block(before_text, "show cdp neighbor")
    after_cdp_block = extract_command_block(after_text, "show cdp neighbor")

    
    before_dt_block = extract_command_block(before_text, "show device-tracking database")
    after_dt_block = extract_command_block(after_text, "show device-tracking database")

    #before_auth_block = extract_command_block(before_text, "show authentication session")
    #after_auth_block = extract_command_block(after_text, "show authentication session")    


    # Parse
    before_ints = parse_show_interface_status(before_int_status_block)
    after_ints = parse_show_interface_status(after_int_status_block)

    before_cdp = parse_show_cdp_neighbor(before_cdp_block)
    after_cdp = parse_show_cdp_neighbor(after_cdp_block)

    
    before_dt = parse_show_device_tracking_database(before_dt_block)
    after_dt = parse_show_device_tracking_database(after_dt_block)

    #before_auth = parse_show_authentication_session(before_dt_block)
    #after_auth = parse_show_authentication_session(after_dt_block)

    # Diffs
    intf_diff = diff_interfaces(before_ints, after_ints)
    cdp_diff = diff_cdp_neighbors(before_cdp, after_cdp)
    dt_diff = diff_device_tracking(before_dt, after_dt)
    #auth_diff = diff_authentication_session(before_auth, after_auth)

    # ---------- Report ----------

    with open(output_file, "w", encoding="utf-8") as f:
        print("=" * 60, file=f)
        print("INTERFACE STATUS / VLAN CHANGES", file=f)
        print("=" * 60, file=f)

        if intf_diff["status_changes"]:
            print("\nStatus changes:", file=f)
            for port, b_status, a_status in intf_diff["status_changes"]:
                print(f"  {port}: status {b_status} -> {a_status}", file=f)
        else:
            print("\nNo interface status changes detected.", file=f)

        if intf_diff["vlan_changes"]:
            print("\nVLAN changes:", file=f)
            for port, b_vlan, a_vlan in intf_diff["vlan_changes"]:
                print(f"  {port}: VLAN {b_vlan} -> {a_vlan}", file=f)
        else:
            print("\nNo VLAN changes detected.", file=f)

        if intf_diff["only_in_before"]:
            print("\nInterfaces only in BEFORE (missing in AFTER):", file=f)
            for port in intf_diff["only_in_before"]:
                print(f"  {port}", file=f)

        if intf_diff["only_in_after"]:
            print("\nInterfaces only in AFTER (new or renamed?):", file=f)
            for port in intf_diff["only_in_after"]:
                print(f"  {port}", file=f)

        print("\n" + "=" * 60, file=f)
        print("CDP NEIGHBOR CHANGES", file=f)
        print("=" * 60, file=f)

        if cdp_diff["removed"]:
            print("\nNeighbors removed:", file=f)
            for device_id, port_id, b_local in cdp_diff["removed"]:
                print(f"  {device_id} ({port_id}) was on {b_local}, now gone", file=f)

        if cdp_diff["added"]:
            print("\nNeighbors added:")
            for device_id, port_id, a_local in cdp_diff["added"]:
                print(f"  {device_id} ({port_id}) newly seen on {a_local}", file=f)

        if cdp_diff["moved"]:
            print("\nNeighbors moved (same remote, different local port):", file=f)
            for device_id, port_id, old_local, new_local in cdp_diff["moved"]:
                print(f"  {device_id} ({port_id}) moved: {old_local} -> {new_local}", file=f)

        if not (cdp_diff["removed"] or cdp_diff["added"] or cdp_diff["moved"]):
            print("\nNo CDP neighbor changes detected.", file=f)



    
        print("\n" + "=" * 60, file=f)
        print("DEVICE TRACKING DATABASE CHANGES", file=f)
        print("=" * 60, file=f)

        if dt_diff["removed"]:
            print("\nEndpoints removed (seen BEFORE, not AFTER):", file=f)
            for addr in dt_diff["removed"]:
                b = before_dt[addr]
                print(
                    f"  {addr}: {b.code} {b.mac} on {b.interface} VLAN {b.vlan} "
                    f"(state {b.state}, prlvl {b.prlvl})", file=f
                )

        if dt_diff["added"]:
            print("\nEndpoints added (seen AFTER, not BEFORE):", file=f)
            for addr in dt_diff["added"]:
                a = after_dt[addr]
                print(
                    f"  {addr}: {a.code} {a.mac} on {a.interface} VLAN {a.vlan} "
                    f"(state {a.state}, prlvl {a.prlvl})", file=f
                )

        if not (dt_diff["removed"] or dt_diff["added"] or dt_diff["changed"]):
            print("\nNo device-tracking changes detected.", file=f)


        print("\nDone.", file=f)
        
        if dt_diff["removed"]:
            print("\nCommands to bounce ports:\n", file=f)
            dedup_interfaces = []
            for addr in dt_diff["removed"]:
                b = before_dt[addr]
                if b.interface not in dedup_interfaces:
                    dedup_interfaces.append(b.interface)
                    print(
                        f"int {b.interface}",
                        f" shut", 
                        sep="\n", 
                        file=f
                    )
            print("\n\nWait a bit, then re-enable:\n\n", file=f)
            dedup_interfaces = []
            for addr in dt_diff["removed"]:
                b = before_dt[addr]
                if b.interface not in dedup_interfaces:
                    dedup_interfaces.append(b.interface)
                    print(
                        f"int {b.interface}",
                        f" no shut", 
                        sep="\n", 
                        file=f
                    )


if __name__ == "__main__":
    for before_file, after_file in zip(os.listdir(os.path.join(active_folder, "Prechange Logs")), os.listdir(os.path.join(active_folder, "Postchange Logs"))):
        print(f"\n\nComparing {before_file} to {after_file}...")
        before_path = os.path.join(active_folder, "Prechange Logs", before_file)
        after_path = os.path.join(active_folder, "Postchange Logs", after_file)
        output_path = os.path.join(active_folder, f"{before_file.split(" ")[0]} comp.txt")
        post_check(before_path, after_path, output_path)



    
    