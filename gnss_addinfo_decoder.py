from serial import Serial
from pyubx2 import UBXReader
from pyubx2 import UBXMessage, SET
from datetime import datetime
import time
from rich.live import Live
from rich.table import Table
from rich import box
from rich import print
from rich.layout import Layout
import csv
import os
import argparse
from bitstring import BitArray
tab = []
dcr_tab = []
gal_str = ''
qzss_str = ''
reset_time = int(time.time())

parser = argparse.ArgumentParser(description='RLS/DCR message decoder')
parser.add_argument('serialport', type=str, help='U-blox receiver COM-port')
parser.add_argument('--out_rlm_file', type=str, help='RLM CSV log file', default='RLM_log.csv')
parser.add_argument('--out_dcr_file', type=str, help='DCR CSV log file', default='DCR_log.csv')
parser.add_argument('--hide_qzss', type=str, help='hide QZSS DCR table', action=argparse.BooleanOptionalAction)
parser.add_argument('--hide_rlm', type=str, help='hide RLM table', action=argparse.BooleanOptionalAction)
parser.add_argument('--autoconf', type=str, help='receiver autoconfiguration', action=argparse.BooleanOptionalAction)
parser.add_argument('--autodel', type=int, help='delete tables every 6 hours', action=argparse.BooleanOptionalAction)

args = parser.parse_args()

dcr_msg_types = {1: 'Earthquake EW',
                 2: 'Hypocenter',
                 3: 'Seismic Intensity',
                 4: 'Nankai Trough Earthquake',
                 5: 'Tsunami',
                 6: 'NW Pacific Tsunami',
                 7: 'Unused',
                 8: 'Volcano',
                 9: 'Ash Fall',
                 10: 'Weather',
                 11: 'Flood',
                 12: 'Typhoon',
                 13: 'Unused',
                 14: 'Marine'}

dcr_tsunami_height = {1: '<0.2m',
                      2: '1m',
                      3: '3m',
                      4: '5m',
                      5: '10m',
                      6: '>10m',
                      14: 'UNKN',
                      15: 'other',}

dcr_np_tsunami_height = {1: '0.3m-1m',
                      2: '1m-3m',
                      3: '3m-5m',
                      4: '5m-10m',
                      508: '>10m',
                      509: 'high',
                      510: 'very high',
                      511: 'UNKN',}

dcr_flood_warn = {1: 'Alarm',
                  2: 'Warning',
                  3: 'Risk',
                  4: 'Occurrence',
                  15: 'Other'}

dcr_typhoon_scale = {0: 'None',
                  1: 'Large',
                  2: 'Extra large',
                  15: 'Other'}

dcr_typhoon_intensity = {0: 'None',
                  1: 'Strong',
                  2: 'Very strong',
                  3: 'Ferocious',
                  15: 'Other'}

dcr_marine_warncode = {0: 'Warning canceled',
                  10: 'Ice',
                  11: 'Fog',
                  12: 'Swell',
                  20: 'Wind',
                  21: 'Gale',
                  22: 'Storm',
                  23: 'Typhoon',
                  31: 'Other'}

dcr_weather_type = {1: 'Snow storm',
                    2: 'Heavy rain',
                    3: 'Storm',
                    4: 'Heavy snow',
                    5: 'Wave warning',
                    6: 'Storm surge',
                    7: 'Special warning',
                    21: 'Record-breaking heavy rain',
                    22: 'Tornado',
                    23: 'Landslide',
                    31: 'Other'}

dcr_seismic_intlow = {1: '0',
                      2: '1',
                      3: '2',
                      4: '3',
                      5: '4',
                      6: 'lower 5',
                      7: 'upper 5',
                      8: 'lower 6',
                      9: 'upper 6',
                      10: '7',
                      14: 'Nothing',
                      15: 'UNKN'}

dcr_seismic_inthigh = {1: '0',
                      2: '1',
                      3: '2',
                      4: '3',
                      5: '4',
                      6: 'lower 5',
                      7: 'upper 5',
                      8: 'lower 6',
                      9: 'upper 6',
                      10: '7',
                      11: '>7',
                      14: 'Nothing',
                      15: 'UNKN'}


with open('country.csv') as f:
    countrylist = csv.DictReader(f, delimiter=';')
    countrydict = {rows['Code']:rows['Country'] for rows in countrylist}

if not os.path.isfile(args.out_rlm_file):
    with open(args.out_rlm_file, 'w', newline='\n') as csvfile:
        rlmlog = csv.writer(csvfile, delimiter=';')
        rlmlog.writerow(['SAT', 'BEACON HEXID', 'TYPE', 'COUNTRY', 'SEEN', 'Message', 'Params'])

if not os.path.isfile(args.out_dcr_file):
    with open(args.out_dcr_file, 'w', newline='\n') as csvfile:
        rlmlog = csv.writer(csvfile, delimiter=';')
        rlmlog.writerow(['RECEIPT TIME', 'SAT', 'PRIORITY', 'CATEGORY', 'REPORT TIME', 'INFO TYPE', 'INFO'])

def country_decode (beacon) :
    t = bin(int(beacon, 16))[2:].zfill(60)
    t = t[1:11]
    try:
        country = countrydict[str(int(t,2))]
        return country
    except KeyError:
        return "UNKNOWN"

def dict_except(dict,key):
    try:
        return dict[key]
    except KeyError:
        return 'Err'

def beacon_type(beacon) :
    t = bin(int(beacon, 16))[2:].zfill(60)
    if t[0] == '1' :
        match t[11:14] :
            case '010' | '110':
                return 'EPIRB'
            case '111' :
                return 'TEST'
            case '000' :
                return 'ORB'
            case '001' :
                return 'ELT'
            case '011' :
                match t[14:17] :
                    case '000' | '001' | '011':
                        return 'ELT'
                    case '010' | '100' :
                        return 'EPIRB'
                    case '110' :
                        return 'PLB'
                    case _ :
                        return "UNDEF"
            case '100' :
                return 'NUP'
            case '101' :
                return 'SGB'
            case _:
                return 'UNDEF'
    else:
        match t[11:15] :
            case '0010' | '1010' | '0110':
                return 'EPIRB'
            case '0011' | '0100' | '0101' | '1000' | '1001' :
                return 'ELT'
            case '0111' | '1011' :
                return 'PLB'
            case '1100' :
                return 'ShipSec'
            case '1110' | '1111' :
                return 'TEST'
            case '1101' :
                if t[17:21] == '1111':
                    if t[15:17] == '00': return 'RLS/1st EPIRB'
                    elif t[15:17] == '01': return 'RLS/2nd EPIRB'
                    elif t[15:17] == '10': return 'RLS/PLB EPIRB'
                    else: return 'RLS/TEST EPIRB'
                else:
                    if t[15:17] == '00': return 'RLS/ELT'
                    elif t[15:17] == '01': return 'RLS/EPIRB'
                    elif t[15:17] == '10': return 'RLS/PLB'
                    else: return 'RLS/TEST'
            case _:
                return 'UNDEF'
            
def new_row(parsed_data,s) :
    temprow = []
    now = datetime.now().strftime("%H:%M %d-%m")
    temprow.append(parsed_data.svId)
    temprow.append(s.upper())
    temprow.append(beacon_type(s))
    temprow.append(country_decode(s))
    temprow.append(str(now))
    temprow.append(1)
    tolog = temprow[:-1]
    tolog.append(bin(parsed_data.message)[2:].zfill(4))
    if parsed_data.type == 1:
        tolog.append(bin(parsed_data.params)[2:].zfill(16))
    else: tolog.append(bin(parsed_data.params)[2:].zfill(96))
    with open(args.out_rlm_file, 'a', newline='') as csvfile:
        writer_object = csv.writer(csvfile, delimiter=';')
        writer_object.writerow(tolog)
    return temprow

def dcr_parse_row(dcr_bin_str,svid) :
    dcr_row =[]
    dcr_row.append(str(datetime.now().strftime("%H:%M %d-%m")))
    dcr_row.append(str(svid))
    btod = lambda s, po : str(dcr_bin_str[s:po].uint)
    dcr_row.append(btod(14,17))
    if btod(8,14) == '44':
       dcr_row.append('OTHER ORG')
       dcr_row.append('None')
       dcr_row.append('None')
       dcr_row.append(f'Organization code:{btod(17,23)}')
       dcr_row.append(dcr_bin_str.bin[8:41])
       return dcr_row
    dcr_row.append(dict_except(dcr_msg_types,dcr_bin_str[17:21].uint))
    string = f'{btod(25,30)}/{btod(21,25)} {btod(30,35)}:{btod(35,41)}'
    dcr_row.append(string)
    if dcr_bin_str[41:43].uint == 0 : dcr_row.append('Issue')
    elif dcr_bin_str[41:43].uint == 1: dcr_row.append('Correction')
    else: dcr_row.append('Cancellation')
    match dcr_bin_str[17:21].uint:
        case 1 :    # Earthquake Early Warning
            tempstr = ''
            tempstr += f'DP codes: {btod(53,62)}, {btod(62,71)}, {btod(71,80)}.\n'
            tempstr += f'Time of EQ: {btod(85,90)}:{btod(90,96)} DoM:{btod(80,85)}\n'
            tempstr += f'Depth of epicenter {btod(96,105)}. '
            tempstr += f'Magnitude {str(dcr_bin_str[105:112].uint/10)}\n'
            tempstr += f'Ep. region {btod(112,122)}. '
            tempstr += f'Seismic intensity from {dict_except(dcr_seismic_intlow,dcr_bin_str[122:126].uint)} to {dict_except(dcr_seismic_inthigh,dcr_bin_str[126:130].uint)}\n'
            tempstr += f'Region mask {dcr_bin_str[130:210].hex}\n'
            dcr_row.append(tempstr)
        case 2 :    # Hypocenter
            tempstr = ''
            tempstr += f'DP codes: {dcr_bin_str[53:62].uint}, {dcr_bin_str[62:71].uint}, {dcr_bin_str[71:80].uint}. '
            tempstr += f'Time of EQ : {btod(85,90)}:{btod(90,96)} DoM:{btod(80,85)}\n'
            tempstr += f'Depth of epicenter {btod(96,105)}. '
            tempstr += f'Magnitude {str(dcr_bin_str[105:112].uint/10)}\n'
            tempstr += f'Seismic epicenter {btod(112,122)} '
            lat = 'N' if dcr_bin_str[122:123].bin == '0' else 'S'
            tempstr += f'{btod(123,130)}°{btod(130,136)}\'{btod(136,142)}\"{lat} '
            lon = 'E' if dcr_bin_str[142:143].bin == '0' else 'W' 
            tempstr += f'{btod(143,151)}°{btod(151,157)}\'{btod(157,163)}\"{lon} '
            dcr_row.append(tempstr)
        case 3 :    # Seismic Intensity
            tempstr = ''
            tempstr += f'Time of earthquake : {btod(58,63)}:{btod(63,69)} DoM:{btod(53,58)}\n'
            tempstr += 'Prefecture:Int. : '
            for i in range(16) :
                if btod(69+i*9,78+i*9) == '0':
                    break
                intens = 69+i*9
                reg = 72+i*9
                tempstr += f'{btod(reg,reg+6)}:{btod(intens,intens+3)} '
            dcr_row.append(tempstr)
        case 4:     # Nankai Trough Earthquake
             tempstr = ''
             tempstr += f'Serial Code: {btod(53,57)} Text:\n'
             for i in range(18):
                if btod(57+i*8,65+i*8) == '0':
                    break
                try:
                     chart = bytes.fromhex(dcr_bin_str[57+i*8:65+i*8].hex).decode("utf-8")
                except UnicodeDecodeError:
                    chart = '*'
                tempstr += chart
             dcr_row.append(tempstr)
        case 5:     # Tsunami
             tempstr = ''
             tempstr += f'DP codes: {btod(53,62)}, {btod(62,71)}, {btod(71,80)}. '
             tempstr += f'Warn. Code: {btod(80,84)}\n'
             for i in range(5):
                if btod(84+i*26,110+i*26) == '0':
                    break 
                tempstr += f'Region:{btod(100+i*26,110+i*26)}, '               
                day = 'today' if btod(84+i*26,85+i*26) == '0' else 'tomorrow'
                tempstr += f'{day} {btod(85+i*26,90+i*26)}:{btod(90+i*26,96+i*26)}, Height: {dict_except(dcr_tsunami_height,dcr_bin_str[96+i*26:100+i*26].uint)}\n'   
             dcr_row.append(tempstr)
        case 6:     # Northwest Pacific Tsunami
            tempstr = ''
            tempstr += f'Potential: {btod(53,56)}\n'
            for i in range(5):
                if btod(56+i*28,84+i*28) == '0':
                    break 
                tempstr += f'Region:{btod(77+i*28,84+i*28)}, '
                day = 'today' if btod(56+i*28,57+i*28) == '0' else 'tomorrow'
                tempstr += f'{day} {btod(57+i*28,62+i*28)}:{btod(62+i*28,68+i*28)}, Height: {dict_except(dcr_np_tsunami_height,dcr_bin_str[68+i*28:77+i*28].uint)} '

            dcr_row.append(tempstr)
        case 8:     # Volcano
            tempstr = ''
            tempstr += f'Time type code:{btod(50,53)} '
            act_time = ' unknown' if btod(58,63) == '31' and btod(63,69) == '63' else f'{btod(58,63)}:{btod(63,69)} DoM:{btod(53,58)}'
            tempstr += f'Activity time:{act_time}\n'
            tempstr += f'Warning code:{btod(69,76)} '
            tempstr += f'Volcano name:{btod(76,88)}\n Local Gov.:'
            for i in range(5):
                if btod(88+i*23,111+i*23) == '0':
                    break                 
                tempstr += f'{btod(88+i*23,111+i*23)} '
            dcr_row.append(tempstr)
        case 9:     # Ash Fall
            tempstr = ''
            forecast = '/Preliminary/' if btod(69,71) == '1' else '/Detailed/'
            tempstr += f'{forecast} Activity Time: {btod(58,63)}:{btod(63,69)} DoM:{btod(53,58)}.\nVolcano Name: {btod(71,83)}\n'
            tempstr += 'Expected ash fall time (hours from act.time):AshfallWarnCode:LocGov:\n'
            for i in range(4):
                if btod(83+i*29,112+i*29) == '0':
                    break                
                tempstr += f'{btod(83+i*29,86+i*29)}:{btod(86+i*29,89+i*29)}:{btod(89+i*29,112+i*29)} '
            dcr_row.append(tempstr)
        case 10:    # Weather
            ws = ''
            if btod(53,56) == '1': 
                ws = 'Announcement'
            elif btod(53,56) == '2':
                ws = 'Release'
            else : ws = f'Undef.{btod(53,56)}'
            tempstr = f'Warning state: {ws}\n'
            for i in range(6):
                if (btod(56+i*24,61+i*24) == '0') and (btod(61+i*24,80+i*24) == '0'): break
                tempstr += f'{btod(61+i*24,80+i*24)}:{dict_except(dcr_weather_type,dcr_bin_str[56+i*24:61+i*24].uint)} '
            dcr_row.append(tempstr)
        case 11:    # Flood
            tempstr = 'Region:WarnCode\n'
            for i in range(3):
                if (btod(57+i*44,97+i*44) == '0') and (btod(53+i*44,57+i*44) == '0'): break
                tempstr += f'{btod(57+i*44,97+i*44)}:{dict_except(dcr_flood_warn,dcr_bin_str[53+i*44:57+i*44].uint)} '
            dcr_row.append(tempstr)
        case 12:    # Typhoon
            tempstr = ''
            if btod(69,72) == '1':
                tempstr += '/Analysis/ '
            elif btod(69,72) == '2':
                tempstr += '/Estimate/ '
            else: tempstr += '/Forecast/ '            
            tempstr += f'Reference Time: {btod(58,63)}:{btod(63,69)} DoM:{btod(53,58)}.\n'
            tempstr += f'Elapsed time: {btod(80,87)} hours.'
            tempstr += f'Typhoon number: {btod(87,94)}.\n'
            tempstr += f'Scale category: {dict_except(dcr_typhoon_scale,dcr_bin_str[94:98].uint)} '
            tempstr += f'Intensity category: {dict_except(dcr_typhoon_intensity,dcr_bin_str[98:102].uint)}\n'
            lat = 'N' if dcr_bin_str[102:103].bin == '0' else 'S'
            tempstr += f'{btod(103,110)}°{btod(110,116)}"{btod(116,122)}"{lat} '
            lon = 'E' if dcr_bin_str[122:123].bin == '0' else 'W' 
            tempstr += f'{btod(123,131)}°{btod(131,137)}"{btod(137,143)}"{lon}\n'
            tempstr += f'Central pressure: {btod(143,154)} '
            tempstr += 'Maximum wind speed: '
            if btod(154,161) == '0' : tempstr += 'Unknown'    
            else:  tempstr += btod(154,161)
            tempstr += ' m/s '    
            tempstr += 'Maximum wind gust speed: '
            if btod(161,168) == '0' : tempstr += 'Unknown'    
            else:  tempstr += btod(161,168)
            tempstr += ' m/s'
            dcr_row.append(tempstr)
        case 14:    # Marine
            tempstr = ''
            for i in range(8):
                if (btod(53+i*19,72+i*19) == '0'): break
                tempstr += f'{btod(58+i*19,72+i*19)}:{dict_except(dcr_marine_warncode,dcr_bin_str[53+i*19:58+i*19].uint)} '
            dcr_row.append(tempstr)
        case _:
            tempstr = '--------------'
            dcr_row.append(tempstr)
    dcr_row.append(dcr_bin_str.bin[8:41])
    return dcr_row

def dcr_add_row(row):
    dcr_tab.append(row)
    with open(args.out_dcr_file, 'a', newline='') as csvfile:
        writer_object = csv.writer(csvfile, delimiter=';')
        writer_object.writerow(row[:-1])    


def gen_table() -> Table:
    title_str = f"[bold blue] \nCOSPAS BEACONS RETURN LINK MESSAGES [/bold blue]\n [link=https://cospas-sarsat.int/en/beacons-pro/beacon-message-decode-program-txsep/beacon-decode-2019][i]Link to HEXID decoder[/i][/link] \n GAL SATS: {gal_str}"
    table = Table(show_header=True, header_style="bold", box=box.ROUNDED, border_style="deep_sky_blue4", title=title_str,title_justify='center')
    table.add_column("SAT", header_style="gold3")
    table.add_column("BEACON HEXID", min_width=15, header_style="blue", justify="center")
    table.add_column("TYPE", header_style="orange4", min_width=3, justify="center")
    table.add_column("COUNTRY", header_style="magenta", justify="center",max_width=20)
    table.add_column("LAST SEEN", header_style="sea_green2", justify="center")
    table.add_column("TOTAL", header_style="grey42", justify="center")
    for row in tab :
        if row[2] in ('ORB', 'TEST', 'RLS/TEST EPIRB', 'RLS/TEST') :
            hextid = '[bold][steel_blue1]' + str(row[1]) + '[/steel_blue1][/bold]'
        else:
            hextid = '[bold][red on white]' + str(row[1]) + '[/red on white][/bold]'
        table.add_row(str(row[0]), hextid, row[2], row[3], row[4], str(row[5]))
    dcr_table = Table(show_header=True, header_style="bold", box=box.ROUNDED, show_lines=True,title_justify='center', border_style="deep_sky_blue4", title=f"[bold blue] \nDC REPORTS[/bold blue]\nQZSS SATS: {qzss_str}\n")
    dcr_table.add_column("RECEIPT TIME", header_style="sea_green2", justify="center")
    dcr_table.add_column("SAT", header_style="gold3", justify="center")
    dcr_table.add_column("PRIORITY", header_style="blue", justify="center", min_width=3)
    dcr_table.add_column("CATEGORY", header_style="magenta", justify="center", min_width=7)
    dcr_table.add_column("REPORT TIME", header_style="sea_green2", justify="center",min_width=11)
    dcr_table.add_column("INFO TYPE", header_style="gold3", justify="center")
    dcr_table.add_column("INFO", header_style="blue", justify="center",min_width=25)
    for row in dcr_tab:
        match row[2] :
            case '1' :
                tp = '[bold][red1]MAX[/red1][/bold]'
            case '2' :
                tp = '[bold][gold3]PRIORITY[/gold3][/bold]'
            case '3' :
                tp = '[bold][blue]REGULAR[/blue][/bold]'
            case '7' : 
                tp = 'TRNG/TEST'
            case _:
                tp = f'UNKNOWN "{row[2]}"'
        dcr_table.add_row(row[0],row[1], tp,row[3],row[4],row[5],row[6])
    layout = Layout()
    layout.split_row(
    Layout(table,name="RLM"),
    Layout(dcr_table,name="DCR", minimum_size=120))
    global reset_time
    if args.hide_qzss:
        layout["DCR"].visible = False
    if args.hide_rlm:
        layout["RLM"].visible = False
    if args.autodel:
        if int(time.time()) - reset_time > 21600: # *           Auto delete period
           reset_time = int(time.time())
           tab.clear()
           dcr_tab.clear()
    return layout


if args.autoconf:
    msg_list = []
    serialout = Serial(args.serialport, 38400, timeout=10)
    msg_list.append(UBXMessage('CFG','CFG-GNSS', SET, msgVer=0, numTrkChHw=0, numTrkChUse=255, numConfigBlocks=7, gnssId_01=0, resTrkCh_01=4, maxTrkCh_01=4, reserved0_01=0, enable_01=1, sigCfMask_01=1, gnssId_02=1, resTrkCh_02=0, maxTrkCh_02=0, reserved0_02=0, enable_02=0, sigCfMask_02=1, gnssId_03=2, resTrkCh_03=10, maxTrkCh_03=10, reserved0_03=0, enable_03=1, sigCfMask_03=1, gnssId_04=3, resTrkCh_04=0, maxTrkCh_04=0, reserved0_04=0, enable_04=0, sigCfMask_04=1, gnssId_05=4, resTrkCh_05=0, maxTrkCh_05=0, reserved0_05=0, enable_05=0, sigCfMask_05=1, gnssId_06=5, resTrkCh_06=4, maxTrkCh_06=4, reserved0_06=0, enable_06=1, sigCfMask_06=5, gnssId_07=6, resTrkCh_07=0, maxTrkCh_07=0, reserved0_07=0, enable_07=0, sigCfMask_07=1))
    msg_list.append(UBXMessage('CFG', 'CFG-MSG', SET, msgClass=0x02, msgID=0x59, rateDDC=0, rateUART1=1, rateUART2=0, rateUSB=1, rateSPI=0, reserved=0))
    msg_list.append(UBXMessage('CFG', 'CFG-MSG', SET, msgClass=0x02, msgID=0x13, rateDDC=0, rateUART1=1, rateUART2=0, rateUSB=1, rateSPI=0, reserved=0))
    msg_list.append(UBXMessage('CFG', 'CFG-MSG', SET, msgClass=0x01, msgID=0x35, rateDDC=0, rateUART1=1, rateUART2=0, rateUSB=1, rateSPI=0, reserved=0))
    msg_list.append(UBXMessage('CFG', 'CFG-RATE', SET, measRate=20000, navRate=1, timeRef=1))
    msg_list.append(UBXMessage('CFG', 'CFG-CFG', SET, clearMask=b'\x00\x00\x00\x00', saveMask=b'\xff\xff\x00\x00', loadMask=b'\x00\x00\x00\x00', devBBR=1, devFlash=1, devEEPROM=1, devSpiFlash=0))
    msg_list.append(UBXMessage(b'\x06', b'\x04', SET, payload=b'\xff\xff\x02\x00'))
    for msg in msg_list:
        out = msg.serialize()
        serialout.write(out)
        time.sleep(1)
        print('set params...')
    serialout.close()

#stream = open('out.ubx', 'rb')
stream = Serial(args.serialport, 38400, timeout=30)

with Live(gen_table(), auto_refresh=False) as live:
    ubr = UBXReader(stream, protfilter=2)
    (raw_data, parsed_data) = ubr.read()
    for (raw_data, parsed_data) in ubr:
        if parsed_data.identity == 'RXM-RLM':
            s = BitArray(uintle=parsed_data.beacon, length=64)
            s = str(s.hex)
            s = s[1:]
            if len(tab) > 0 :
                new = True
                for row in tab :
                    if row.count(s.upper()) > 0 :
                        now = datetime.now().strftime("%H:%M %d-%m")
                        row[0] = parsed_data.svId
                        row[4] = str(now)
                        row[5] += 1
                        new = False
                        break
                if new : tab.append(new_row(parsed_data,s))
            else:
                tab.append(new_row(parsed_data,s))
            live.update(gen_table(), refresh=True)
        elif parsed_data.identity == 'RXM-SFRBX' and parsed_data.gnssId == 5 and (str(bin(parsed_data.dwrd_01)).zfill(32)[10:16] in ('101011', '101100')):
            dcr_bin_str = ""
            for i in range(8) :
                temp = BitArray(uint=getattr(parsed_data,f"dwrd_{i+1:02}"), length=32)
                dcr_bin_str += temp.bin
            dcr_bin_str = BitArray(bin=dcr_bin_str)
            if len(dcr_tab) > 0 :
                new = True
                row_c = 0
                for row in dcr_tab:
                    if dcr_bin_str.bin[8:41] == row[7]:
                        dcr_tab[row_c] = dcr_parse_row(dcr_bin_str,parsed_data.svId)
                        new = False
                        break
                    row_c += 1                    
                if new : dcr_add_row(dcr_parse_row(dcr_bin_str,parsed_data.svId))
            else: dcr_add_row(dcr_parse_row(dcr_bin_str,parsed_data.svId))
            live.update(gen_table(), refresh=True)
        elif parsed_data.identity == 'NAV-SAT':
            size = parsed_data.numSvs
            gal_str = ''
            qzss_str = ''
            for i in range(size):
                if getattr(parsed_data, f"gnssId_{i+1:02}") == 2:
                    if getattr(parsed_data, f"qualityInd_{i+1:02}") in(5,6,7):
                        gal_str += f'[bold green3]{getattr(parsed_data, f"svId_{i+1:02}")}[/bold green3] '
                    elif getattr(parsed_data, f"qualityInd_{i+1:02}") == 4:
                        gal_str += f'[bold yellow3]{getattr(parsed_data, f"svId_{i+1:02}")}[/bold yellow3] '                    
                    else:
                        gal_str += f'[bold grey46]{getattr(parsed_data, f"svId_{i+1:02}")}[/bold grey46] '
                elif getattr(parsed_data, f"gnssId_{i+1:02}") == 5:
                    if getattr(parsed_data, f"qualityInd_{i+1:02}") in(5,6,7):                        
                        qzss_str += f'[bold green3]{getattr(parsed_data, f"svId_{i+1:02}")}[/bold green3] '
                    elif getattr(parsed_data, f"qualityInd_{i+1:02}") == 4:
                        qzss_str += f'[bold yellow3]{getattr(parsed_data, f"svId_{i+1:02}")}[/bold yellow3] '                        
                    else:
                        qzss_str += f'[bold grey46]{getattr(parsed_data, f"svId_{i+1:02}")}[/bold grey46] '
            live.update(gen_table(), refresh=True)         