!["preview"](preview.PNG?raw=true)

Return Link Messages (RLM) decoder for COSPAS-SARSAT system. It decodes Galileo RLM and QZSS Reports for disaster and crisis management (DC Reports).

Requirements
==========
— U-blox M8 receiver (3.01 firmware version) or a newer model that supports UBX-RXM-RLM and UBX-RXM-SFRBX messages output and receiving QZSS L1SAIF.

Dependencies
===========

```
pip install pyubx2 rich bitstring 
```

Usage
=============
```
python gnss_addinfo_decoder.py COM-port
python gnss_addinfo_decoder.py -h for additional settings
```
— Port baud rate - 19200.
— If running with a parameter `----autoconf`, the decoder will attempt to autoconfigure the receiver (saving all settings to flash memory), but additional configuration may be required.
— Please make sure that Galileo and QZSS (L1SAIF signal) signals reception is enabled. Also make sure that UBX-RXM-RLM, UBX-RXM-SFRBX and UBX-NAV-SAT messages output is enabled as well.
— The tables are automatically updated after each new message, use Ctrl+С to quit.

Additional information
=========================

[COSPAS-SARSAT](https://cospas-sarsat.int/en/pro)
[Galileo SAR](https://www.gsc-europa.eu/galileo/services/search-and-rescue-sar-galileo-service)
[DCR Interface Specification](https://qzss.go.jp/en/technical/ps-is-qzss/is_qzss_dcr_010_agree.html)