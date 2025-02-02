from dotenv import load_dotenv
from bs4 import BeautifulSoup
from imapclient import IMAPClient
import email
import os
import chardet
import requests

def connect_to_mail(username, password):
    mail = IMAPClient("imap.gmail.com")
    mail.login(username, password)
    mail.select_folder("inbox")
    return mail

def decode_content(content):
    detected_encoding = chardet.detect(content)["encoding"]
    if detected_encoding is None:
        detected_encoding = "utf-8"  # Fallback to UTF-8 if detection fails
    try:
        return content.decode(detected_encoding, errors="ignore")
    except (UnicodeDecodeError, AttributeError):
        print("Could not decode email content")
        return None

def extract_links_from_html(message):
    if message.get_content_type() == "text/html":
        html_content = message.get_payload(decode=True)
        decoded_content = decode_content(html_content)
        if decoded_content:
            soup = BeautifulSoup(html_content, "html.parser")
            for link in soup.find_all("a", href=True):
                # get the text inside the <a> tag
                link_text = link.get_text(strip=True).lower()
                # get the text surrounding the <a> tag
                surrounding_text = link.find_parent().get_text(strip=True).lower()
                if ("unsubscribe" in link_text or "unsubscribe" in surrounding_text) and ("http" in link["href"] or "https" in link["href"]):
                    print("Found a link: " + link["href"])
                    yield link["href"]

def search_for_links(mail):
    mail.idle()
    response = mail.idle_check(timeout=300)
    mail.idle_done()

    if not response:
        mail.noop()
        return

    unread_emails = mail.search('UNSEEN')
    if not unread_emails:
        return

    # RFC822 tells the email server to provide all contents of the email
    fetch_results = mail.fetch(unread_emails, ['RFC822']).items()

    # dictionary containing message id keys, and unsubscribe link values
    message_unsubscribe_links = {}

    for message_id, fetch_result in fetch_results:
        message = email.message_from_bytes(fetch_result[b'RFC822'])

        unsubscribe_links = []
        if message.is_multipart():
            for part in message.walk():
                unsubscribe_links.extend(extract_links_from_html(part))
        else:
            unsubscribe_links.extend(extract_links_from_html(message))

        if unsubscribe_links:
            message_unsubscribe_links[message_id] = unsubscribe_links

    return message_unsubscribe_links

def click_links(unsubscribe_links):
    try:
        for link in unsubscribe_links:
            response = requests.get(link)
            if response.status_code != 200:
                return False
        return True
    except Exception:
        return False

def move_email(mail, message_id, label):
    try:
        mail.move([message_id], label)
        mail.remove_flags([message_id], ["\\Seen"])
    except Exception:
        print("Could not move email to " + label)


def main():
    load_dotenv()
    username = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    mail = connect_to_mail(username, password)

    while True:
            message_unsubscribe_links = search_for_links(mail)
            if message_unsubscribe_links:
                for message_id, unsubscribe_links in message_unsubscribe_links.items():
                    if click_links(unsubscribe_links):
                        move_email(mail, message_id, "unsubscribed")
                    else:
                        move_email(mail, message_id, "to-unsubscribe")


if __name__ == '__main__':
   main()
