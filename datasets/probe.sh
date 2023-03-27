set -x
service dnsmasq stop
service dnsmasq start
ipfixprobe -i 'pcap;ifc=eth1' -p "pstats" -p "phists" -p "tls" -o 'unirec;i=t:4739:timeout=NO_WAIT:buffer=off:autoflush=off;p=(pstats,phists,tls);v'
