import requests
import json
import logging

class GitbotMessageGenerator:

    AUTOFIX_OPT_KEY = "autofix"
    ISSUE_OPT_KEY = "issue"
    REPORT_OPT_KEY = "report"

    __BASE_URL = "https://services3.www.meterian.io/api/v1/gitbot/results/parse"
    __log =  logging.getLogger("GitbotMessageGenerator")

    def __init__(self):
        pass

    def genMessage(self, report: map, options: map) -> map:
        body = { "report": report, "options": options }
        headers = {"Content-Type": "application/json"}
        response = requests.post(self.__BASE_URL, data = json.dumps(body), headers = headers)
        if response.status_code == 200:
            return json.loads(response.text)
        else:
            self.__log.error("Unsuccessful call to gitbot\nStatus code: %s\nResponse: %s", str(response.status_code), response.text)
            return None