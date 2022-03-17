import requests

url = "http://10.1.10.70:2017/AlarmHandleService.asmx"

payload = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\r\n<soap:Envelope xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns:xsd=\"http://www.w3.org/2001/XMLSchema\" xmlns:soap=\"http://schemas.xmlsoap.org/soap/envelope/\">\r\n  <soap:Body>\r\n    <AlarmSendWithParam xmlns=\"http://uniworks.alarm/\">\r\n      <alarmSendWithParamMessage>\r\n        <FactoryID>K1</FactoryID>\r\n        <SubSystemID>GSS</SubSystemID>\r\n        <EqpID></EqpID>\r\n        <AlarmInfoID>AC_GSS_120808</AlarmInfoID>\r\n        <AlarmSubject>Motion-Alarm123</AlarmSubject>\r\n        <AlarmContent>XXXXXXX</AlarmContent>\r\n        <AlarmContentType>TEXT</AlarmContentType>\r\n        <ReceiveType></ReceiveType>\r\n        <FilterParam></FilterParam>\r\n        <InfoParam></InfoParam>\r\n      </alarmSendWithParamMessage>\r\n    </AlarmSendWithParam>\r\n  </soap:Body>\r\n</soap:Envelope>"
headers = {
  'Content-Type': 'text/xml; charset=utf-8'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)