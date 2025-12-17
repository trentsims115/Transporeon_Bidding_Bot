import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_acception_email(receiver, bot_name, load):
    sender = f'{bot_name}_bot@paulinc.com'

    bid_amount = load.get("amount", "N/A")
    reason = load.get("reason", "N/A")

    email_html = f"""
    <html>
        <body>
            <p><strong>Load Accepted:</strong> 
                <a href='https://market-atl.carrierpoint.com/market/jsp/CPShipmentDetail.jsp?shipmentId={load["id"]}'>
                    {load["id"]}
                </a> 
                - {load["origin_city"]}, {load["origin_state"]} → {load["destn_city"]}, {load["destn_state"]}
            </p>

            <p><strong>Shipper:</strong> {load["shipper"]}</p>
            <p><strong>Pickup Date:</strong> {load["pickup_date"]}</p>

            <p><strong>Bid Placed:</strong> ${bid_amount}</p>
            <p><strong>Reason:</strong> {reason}</p>
        </body>
    </html>
    """

    # Create a MIMEMultipart message
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(receiver)
    msg['Subject'] = f'Load Bid {load["id"]} - Bid ${bid_amount}'

    # Attach HTML content
    msg.attach(MIMEText(email_html, 'html'))

    with smtplib.SMTP(host='paulinc-com.mail.eo.outlook.com', port=25) as server:
        server.ehlo()
        server.starttls()
        server.send_message(msg)

    print(f'Successfully sent email to {receiver}')


def send_login_failure_email(receiver, bot_name):
    sender = f'{bot_name}_bot@paulinc.com'
    subject = f'{bot_name} Login Failure'
    email_html = f"""
    <html>
        <body>
            <p><strong>{bot_name}</strong> encountered a login failure.</p>
            <p>Please check credentials, CAPTCHA, or network connection for this bot.</p>
            <p>Timestamp: <b>Check bot logs for exact time.</b></p>
        </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(receiver)
    msg['Subject'] = subject
    msg.attach(MIMEText(email_html, 'html'))

    with smtplib.SMTP(host='paulinc-com.mail.eo.outlook.com', port=25) as server:
        server.ehlo()
        server.starttls()
        server.send_message(msg)

    print(f'Successfully sent login failure email to {receiver}')


def send_linehaul_load_found_email(receiver, bot_name):
    sender = f'{bot_name}_bot@paulinc.com'
    subject = f'{bot_name} Linehaul Load Found'
    email_html = f"""
    <html>
        <body>
            <p><strong>{bot_name}</strong> detected a new linehaul load opportunity.</p>
            <p>The bot has identified a load that meets linehaul criteria.</p>
            <p>Please review the system logs or dashboard for full details.</p>
        </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(receiver)
    msg['Subject'] = subject
    msg.attach(MIMEText(email_html, 'html'))

    with smtplib.SMTP(host='paulinc-com.mail.eo.outlook.com', port=25) as server:
        server.ehlo()
        server.starttls()
        server.send_message(msg)

    print(f'Successfully sent linehaul load found email to {receiver}')

def send_error_email(receiver, bot_name, error):
    sender = f'{bot_name}_bot@paulinc.com'
    subject = f'{bot_name} Error Submitting Bid'
    email_html = f"""
    <html>
        <body>
            <p><strong>{bot_name}</strong> has run into an error when trying to submit a bid</p>
            <p>{error}</p>
        </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = ', '.join(receiver)
    msg['Subject'] = subject
    msg.attach(MIMEText(email_html, 'html'))

    with smtplib.SMTP(host='paulinc-com.mail.eo.outlook.com', port=25) as server:
        server.ehlo()
        server.starttls()
        server.send_message(msg)

    print(f'Successfully sent error email to {receiver}')
