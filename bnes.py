from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from lxml import html
import os

import slack
import twitter
import requests
import smtplib
import yaml


def get_page(url):
    # todo need some error checking
    pagecontent = requests.get(url)
    return pagecontent


def get_collections(pagehtml):
    dateformat = '%A, %d %B %Y'
    tree = html.fromstring(pagehtml.content)
    trs = tree.xpath("//table[@id='reftab']/*")
    collist = list()
    for tr in trs:
        d = dict()
        coltype = str(tr.xpath("td")[0].xpath("strong/text()")[0]).split(":")[0]
        try:
            # Sometimes the council website doesn't have the date info, in which case skip that collection type
            coldate = datetime.strptime(tr.xpath("td")[0].xpath("span/text()")[0], dateformat)
        except IndexError:
            continue
        d['description'] = coltype.replace("Your next ", "")\
                                  .replace("collection is", "")\
                                  .capitalize()
        d['date'] = coldate.date()
        d['date_string'] = coldate.strftime("%a %e")
        collist.append(d)
    return collist


def load_config():
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(proj_dir, "config.yml")
    conf = yaml.safe_load(open(config_path))
    return conf


def notify(c):
    config = load_config()
    users = config['users']

    msgtxt = '{}tomorrow, {}'.format(c['description'], c['date_string'])

    if config['SEND_NOTIFICATION']:
        for user in users:
            if user['method'] == "twitter":
                api = twitapi()
                try:
                    api.PostDirectMessage(msgtxt, user['contact'])
                except KeyError:
                    # error from python-twitter if the bot doesn't follow the recipient
                    pass

            elif user['method'] == "email":
                email_user = config['email-sender']['username']
                password = config['email-sender']['password']
                serv = smtplib.SMTP(host=config['email-sender']['host'],
                                    port=config['email-sender']['port'])
                serv.starttls()
                serv.login(email_user, password)

                msg = MIMEText("")

                msg['From'] = "{} <{}>".format(config['email-sender']['name'], email_user)
                msg['To'] = user['contact']
                msg['Subject'] = msgtxt

                try:
                    serv.send_message(msg)
                except smtplib.SMTPException as e:
                    # todo: should retry some errors, and log others
                    pass

                del msg
            elif user['method'] == "slack":
                slack_token = config['slack_login']['bot_token']
                client = slack.WebClient(token=slack_token)

                response = client.chat_postMessage(
                    channel=user['contact'],
                    text=msgtxt)
                assert response["ok"]
    else:
        print(msgtxt)


def twitapi():
    config = load_config()

    api = twitter.Api(config['twitter-api']['consumer_key'],
                      config['twitter-api']['consumer_secret'],
                      config['twitter-api']['access_key'],
                      config['twitter-api']['access_secret'])

    return api


if __name__ == '__main__':
    config = load_config()
    page = get_page(config['target-url'])
    cols = get_collections(page)

    tomorrow = date.today() + timedelta(days=1)
    
    for col in cols:
        if config['ignore-date-check'] or col['date'] == tomorrow:
            notify(col)
