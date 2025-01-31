from dotenv import load_dotenv
from bs4 import BeautifulSoup
from imapclient import IMAPClient
import email
import imaplib
import os
import chardet
import requests

load_dotenv()

username = os.getenv("EMAIL")
password = os.getenv("PASSWORD")

def connect_to_mail():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(username, password)
    mail.select("inbox")

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
    # try:
    if message.get_content_type() == "text/html":
        html_content = message.get_payload(decode=True)
        decoded_content = decode_content(html_content)
        if decoded_content:
            soup = BeautifulSoup(html_content, "html.parser")
            yield [link["href"] for link in soup.find_all("a", href=True) if "unsubscribe" in link["href"].lower()]


def click_link(link):
    try:
        response = requests.get(link)
        if response.status_code != 200:
            print("Error code", response.status_code, "when unsubscribing from", link)
    except Exception as e:
        print("Error unsubscribing from", link, e)


def search_for_email():
    mail = connect_to_mail()
    # Find emails with 'unsubscribe' in the body of the email.
    _, search_data = mail.search(None, '(BODY "unsubscribe")')
    data = search_data[0].split()

    links = []

    for num in data:
        # RFC822 tells the email server to provide all contents of the email
        _, data = mail.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        if msg.is_multipart():
            for part in msg.walk():
                links.extend(extract_links_from_html(part))
        else:
            links.extend(extract_links_from_html(msg))


    mail.logout()
    return links


links = search_for_email()
# for link in links:
#     click_link(link)
print(links)