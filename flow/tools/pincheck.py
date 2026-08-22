# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2024 RVLab Contributors

import csv
from lxml import objectify
from types import SimpleNamespace
from collections import namedtuple

SignalPin = namedtuple('SignalPin', ['pin_number', 'use', 'io_standard', 'pull_type'])

def read_pin_report_xml(filename) -> list[dict[str, str]]:
    with open(filename, "br") as f:
        data = objectify.fromstring(f.read())
    tab = data.section[1].table
    col_title = [h.get('contents') for h in tab.tablerow[0].tableheader]
    pins = [{k: col.get('contents') for k, col in zip(col_title, row.tablecell)} for row in tab.tablerow[1:]]
    return [SimpleNamespace(**{k.lower().replace(" ", "_").replace('-', '_'): v.strip() for k, v in pin.items()}) for pin in pins]

#signalpin_by_pin = {c.pin_number: c for c in self.signal}
def signalpins_from_xml(filename):
    res={}
    for p in read_pin_report_xml(filename):
        if p.use in ('VCCO', 'GND', 'Config', 'VCCAUX', 'VCCINT'):
            continue
        if p.signal_name == '':
            continue
        res[p.signal_name] = SignalPin(p.pin_number, p.use, p.io_standard, p.pull_type)

    return res

def signalpins_from_csv(filename):
    res = {}
    with open(filename) as f:
        reader = csv.DictReader(f)

        for row in reader:
            signal_name = row['signal_name']
            if signal_name in res:
                raise Exception(f"Duplicate signal name {signal_name}.")
            res[signal_name] = SignalPin(row['pin_number'], row['use'], row['io_standard'], row['pull_type'])

    return res

def signalpins_to_csv(filename, pins):
    with open(filename, 'w', newline='') as f:
        spamwriter = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        spamwriter.writerow(('signal_name', 'pin_number', 'use', 'io_standard', 'pull_type'))
        for k, v in pins.items():
            spamwriter.writerow((k, v.pin_number, v.use, v.io_standard, v.pull_type))

class SignalpinCheckException(Exception):
    pass

def signalpins_check(observed, ref):
    report = []
    error = False
    pins_missing_in_ref = set(observed.keys()) - set(ref.keys())
    if len(pins_missing_in_ref) == 0:
        report.append("No pins missing in reference.")
    else:
        report.append(f"ERROR: Unexpected additional pins in design: {pins_missing_in_ref}")
        error = True
    
    pins_missing_in_observed =  set(ref.keys()) - set(observed.keys())
    if len(pins_missing_in_observed) == 0:
        report.append("No pins missing in observed.")
    else:
        report.append(f"ERROR: Missing pins in design: {pins_missing_in_observed}")
        error = True

    signal_names_matching = set(ref.keys()) & set(observed.keys()) 
    pins_matching = []
    for signal_name in signal_names_matching:
        o = observed[signal_name]
        r = ref[signal_name]
        if o == r:
            pins_matching.append(signal_name)
        else:
            report.append(f"ERROR: Design pin {signal_name} ({o}) does not match reference specification ({r}).")
            error = True

    report.append(f"Pins matching reference: {', '.join(pins_matching)}")

    print("\n".join(report))
    if error:
        raise SignalpinCheckException("Mismatch in signal pin check.")

    return report
