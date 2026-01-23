import os, base64
import requests, ujson
'''
Note to the Developer:
    When calling DAT, trip data needs to be provided in multi-stop format so that the an accurate route is retrieved.

    For your convenience, we've summarized the DAT call process here:
    Make DAT Call
        Step 1 - Fetch DAT credentials from environment variables
        Step 2 - Normalize Phoenix System, incoming equipment type data to DAT equipment type code.
        Step 3 - Generate request body For DAT - https://analytics.api.dat.com/linehaulrates/v1/lookups
        Step 4 - Make API request to DAT - https://analytics.api.dat.com/linehaulrates/v1/lookups
        Step 5 - If the DAT token(s) has expired, regenerate org_token and user_token and store the new tokens.
        Step 6 - Make another API request for DAT - https://analytics.api.dat.com/linehaulrates/v1/lookups
'''

_ORG_BEARER_TOKEN = 'ABC'
_USER_BEARER_TOKEN = 'XYZ'

def make_dat_call(load, time_frame="none"):
    global _ORG_BEARER_TOKEN
    global _USER_BEARER_TOKEN

    #Step 1: Fetching DAT creds from environment variables
    org_username = 'Datapi.Service@paulinc.com'
    org_password = '2059462163@Ddat'
    user_level_username = 'Smithers.Dat@paulinc.com'
        
    dat_lookup_req = [
        {
            'origin': {
                'city': load['origin_city'],
                'stateOrProvince': load['origin_state']
            },
            'destination': {
                'city': load['dest_city'],
                'stateOrProvince': load['dest_state']
            },
            'equipment': load['equipment'],
            'includeMyRate': False,
            'rateType': 'SPOT'
        }
    ]
    if time_frame == "average":
        dat_lookup_req['targetEscalation'] = {
            "escalationType": "SPECIFIC_TIME_FRAME_AND_SMALLEST_AREA_TYPE",
            "specificTimeFrame": "90_DAYS"
        }

    #Step 2 & 3
    equipment_type = load['equipment']
    dat_equipment_code = equipment_type.upper()
    if "V" in equipment_type.upper() or "VAN" == equipment_type.upper():
        dat_equipment_code = "VAN"
    elif equipment_type.lower() in ["reefer"]:
        dat_equipment_code = "REEFER"
    elif "FB" in equipment_type.upper() or "FLAT" in equipment_type.upper() or "FLT" in equipment_type.upper():
        dat_equipment_code = "FLATBED"
    dat_lookup_req[0]['equipment'] = dat_equipment_code
    load['dat_equipment'] = dat_equipment_code
    #Step 4
    dat_lookup_url = 'https://analytics.api.dat.com/linehaulrates/v1/lookups'
    dat_lookup_headers = {'Authorization':_USER_BEARER_TOKEN,'Content-Type': 'application/json'}
    dat_lookup_resp =  requests.post(dat_lookup_url, data=ujson.dumps(dat_lookup_req), headers=dat_lookup_headers)
    if(dat_lookup_resp.status_code in [200, 201]):  #the cached / stored tokens worked and DAT responded correctly
        dat_lookup_data = ujson.loads(dat_lookup_resp.text)
        for response in dat_lookup_data['rateResponses']:
            if 'errors' in response['response']:
                return { 'status': 'failed', 'message': 'Error in response: ' + response['response']['errors'][0]['message'], 'error_code': dat_lookup_resp.status_code }
        dat_lookup_data = ujson.loads(dat_lookup_resp.text)
        return {'status':'ok', 'response':dat_lookup_data}
    
    elif(dat_lookup_resp.status_code in [401, 403]): #(dat response code 401, 403) token needs to be regenerated / refetched from DAT
        #Start the process for fetching the org token
        dat_token_org_req = {'username': org_username, 'password': org_password}
        dat_token_org_url = 'https://identity.api.dat.com/access/v1/token/organization'
        dat_token_org_headers = {'Content-Type': 'application/json'}
        dat_token_org_resp = requests.post(dat_token_org_url, data=ujson.dumps(dat_token_org_req), headers=dat_token_org_headers )

        if(dat_token_org_resp.status_code in [200, 201]):   #The org token request has now worked
            dat_token_org_data = ujson.loads(dat_token_org_resp.text)
            _ORG_BEARER_TOKEN = 'Bearer ' + dat_token_org_data['accessToken']
        else: 
            return {'status':'failed', 'message':f'Error Ocurred in Retrieving Organisation token for DAT: {dat_token_org_resp.text}', 'error_code': dat_token_org_resp.status_code}
        
        #Start the process for fetching the user token
        dat_token_user_url = 'https://identity.api.dat.com/access/v1/token/user'
        dat_token_user_req =  {'username': user_level_username}
        dat_token_user_headers = {'Authorization': _ORG_BEARER_TOKEN,'Content-Type': 'application/json'}
        dat_token_user_resp = requests.post(dat_token_user_url, data=ujson.dumps(dat_token_user_req), headers=dat_token_user_headers)

        if(dat_token_user_resp.status_code in [200, 201]):  
            dat_token_user_data = ujson.loads(dat_token_user_resp.text)
            _USER_BEARER_TOKEN = 'Bearer ' + dat_token_user_data['accessToken']
        else:       #token fetch failed
            return {'status':'failed', 'message':f'Error occurred in retrieving User token for DAT: {dat_token_user_resp.text}', 'error_code': dat_token_user_resp.status_code}
        
        #Now make the DAT call all over again with the updated token
        dat_lookup_headers2 = {'Authorization': _USER_BEARER_TOKEN, 'Content-Type': 'application/json'}
        dat_lookup_resp2 = requests.post(dat_lookup_url, data = ujson.dumps(dat_lookup_req), headers=dat_lookup_headers2)

        if dat_lookup_resp2.status_code in [200, 201]:     #DAT rating call worked fine
            dat_lookup_data = ujson.loads(dat_lookup_resp2.text)
            for response in dat_lookup_data['rateResponses']:
                if 'errors' in response['response']:
                    return { 'status': 'failed', 'message': 'Error in response: ' + response['response']['errors'][0]['message'], 'error_code': dat_lookup_resp2.status_code }
            dat_lookup_data = ujson.loads(dat_lookup_resp2.text)
            return {'status':'ok','response': dat_lookup_data}
        else:
            return {'status':'failed','message': f'Error in retrieving rates even though auth was successful: {dat_lookup_resp2.text}', 'error_code': dat_lookup_resp2.status_code}
