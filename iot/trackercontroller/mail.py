import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr

def send_mail(sender, receivers, subject, message, cc, bcc):

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = formataddr((str(Header('SolarTracker Tech Team', 'utf-8')), sender))
    msg['To'] = ", ".join(receivers)
    msg['Cc'] = ','.join(cc)
    msg['Bcc'] = ','.join(bcc)

    msg.attach(MIMEText(message, 'html'))
    print message
    print msg['To']
    try:
       smtpObj = smtplib.SMTP('localhost')
       smtpObj.sendmail(sender, receivers + cc + bcc, msg.as_string())
       print "Successfully sent email"
    except smtplib.SMTPException:
       print "Error: unable to send email"


