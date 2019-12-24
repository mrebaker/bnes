"""
BNES: notifies specified people about local waste collections one day in advance.
"""

from datetime import date, datetime, timedelta
import logging
import os

from email.mime.text import MIMEText
import smtplib

from lxml import html
import requests
import yaml
import slack
import twitter


def get_page(url):
    """
    Fetches a webpage for a given URL.
    :param url: URL for the required webpage.
    :return: A Response object for the request.
    """
    # todo need some error checking

    r = requests.get(url)

    if r.status_code != 200:
        log_date = datetime.now().strftime("%Y-%m-%d %H%M%S")
        filename = f'{log_date} response.html'
        with open(filename, 'w+') as f:
            f.write(r.text)
        logging.critical('get_page failed with status {}. See file {}.'.format(
            r.status_code,
            filename
        ))
        r.raise_for_status()

    return r


def get_collections(page_html):
    """
    Parses the HTML to extract the next dates for each type of collection: bin, recycling, green bin
    Very specific to the webpage layout. Expects iShareMaps which is used by some UK local councils.
    :param page_html: A Response object which should contain a list of waste collections.
    :return: A list of dicts with a human readable description of the collection and
             the date as both datetime and a string.
    """
    date_format = '%A, %d %B %Y'
    tree = html.fromstring(page_html.content)
    trs = tree.xpath("//table[@id='reftab']/*")
    col_list = list()
    for tr in trs:
        col_dict = dict()
        col_type = str(tr.xpath("td")[0].xpath("strong/text()")[0]).split(":")[0]
        try:
            # Sometimes the council website doesn't have the date info
            # in which case skip that collection type
            col_date = datetime.strptime(tr.xpath("td")[0].xpath("span/text()")[0], date_format)
        except IndexError:
            continue
        col_dict['description'] = col_type.replace("Your next ", "")\
                                  .replace("collection is", "")\
                                  .capitalize()
        col_dict['date'] = col_date.date()
        col_dict['date_string'] = col_date.strftime("%a %e")
        col_list.append(col_dict)
    return col_list


def load_config():
    """
    Loads the local configuration file.
    :return: An object representing the config file.
    """
    proj_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(proj_dir, "config.yml")
    conf = yaml.safe_load(open(config_path))
    return conf


def notify(collection):
    """
    Notifies each user of the waste collection using their chosen method: Twitter DM, email, Slack.
    :param collection: a dict representing the given waste collection
    :return: nothing
    """
    users = config['users']

    msg_txt = '{}tomorrow, {}'.format(collection['description'], collection['date_string'])

    if config['SEND_NOTIFICATION']:
        for user in users:
            if user['method'] == "twitter":
                api = twit_api()
                try:
                    api.PostDirectMessage(msg_txt, user['contact'])
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
                msg['Subject'] = msg_txt

                try:
                    serv.send_message(msg)
                except smtplib.SMTPException as error:
                    # todo: should retry some errors, and log others
                    print(error)

                del msg
            elif user['method'] == "slack":
                slack_token = config['slack_login']['bot_token']
                client = slack.WebClient(token=slack_token)

                response = client.chat_postMessage(
                    channel=user['contact'],
                    text=msg_txt)
                assert response["ok"]
    else:
        print(msg_txt)


def twit_api():
    """
    A wrapper for logging into the Twitter API
    :return: an API object
    """
    api = twitter.Api(config['twitter-api']['consumer_key'],
                      config['twitter-api']['consumer_secret'],
                      config['twitter-api']['access_key'],
                      config['twitter-api']['access_secret'])
    # todo: error checking
    return api


if __name__ == '__main__':
    config = load_config()
    logging.basicConfig(filename='bnes.log', format='%(asctime)s %(message)s')
    page = get_page(config['target-url'])
    cols = get_collections(page)

    tomorrow = date.today() + timedelta(days=1)

    for col in cols:
        if config['ignore-date-check'] or col['date'] == tomorrow:
            notify(col)
