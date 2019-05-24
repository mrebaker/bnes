from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from lxml import html

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


def notify(c):
    config = yaml.safe_load(open('config.yml'))
    users = config['users']

    msgtxt = '{}tomorrow, {}'.format(c['description'], c['date_string'])

    if config['SEND_NOTIFICATION']:
        for user in users:
            if user['method'] == "twitter":
                api = twitapi()
                api.PostDirectMessage(msgtxt, user['contact'])

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

                serv.send_message(msg)
                del msg
    else:
        print(msgtxt)


def twitapi():
    config = yaml.safe_load(open('config.yml'))

    api = twitter.Api(config['twitter-api']['consumer_key'],
                      config['twitter-api']['consumer_secret'],
                      config['twitter-api']['access_key'],
                      config['twitter-api']['access_secret'])

    return api


if __name__ == '__main__':
    config = yaml.safe_load(open('config.yml'))
    page = get_page(config['target-url'])
    cols = get_collections(page)

    tomorrow = date.today() + timedelta(days=1)
    
    for col in cols:
        notify(col)
        if col['date'] == tomorrow:
            notify(col)
