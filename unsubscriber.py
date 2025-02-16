from dotenv import load_dotenv
from bs4 import BeautifulSoup
from imapclient import IMAPClient
import email
import os
import chardet
import requests
import traceback

APPROVED_DOMAINS_FILE = "approved_domains.txt"

def connect_to_mail(username, password):
    mail = IMAPClient("imap.gmail.com")
    mail.login(username, password)
    mail.select_folder("inbox")
    print("Successfully connected to email server!")
    return mail

def decode_content(content):
    detected_encoding = chardet.detect(content)["encoding"]
    if detected_encoding is None:
        detected_encoding = "utf-8"  # Fallback to UTF-8 if detection fails
    try:
        return content.decode(detected_encoding, errors="ignore")
    except (UnicodeDecodeError, AttributeError):
        print("Could not decode email content.")
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
                    print(f"Found a link: {link["href"]}.")
                    yield link["href"]

def search_for_links(fetch_results, approved_domains):
    # dictionary containing message id keys, and unsubscribe link values
    message_unsubscribe_links = {}

    for message_id, fetch_result in fetch_results:
        message = email.message_from_bytes(fetch_result[b'RFC822'])

        # if email from list of approved senders, skip this message
        sender = message["From"]
        if sender and any(domain in sender for domain in approved_domains):
            continue

        unsubscribe_links = []
        if message.is_multipart():
            for part in message.walk():
                unsubscribe_links.extend(extract_links_from_html(part))
        else:
            unsubscribe_links.extend(extract_links_from_html(message))

        if unsubscribe_links:
            message_unsubscribe_links[message_id] = unsubscribe_links

    return message_unsubscribe_links

def read_emails(mail):
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
    return mail.fetch(unread_emails, ['RFC822']).items()

def click_links(unsubscribe_links):
    # TODO: there is an issue here - if the link redirects to some website where more information is required, the
    # return code will be 200, but the unsubscribe attempt will not have been successful
    for link in unsubscribe_links:
        try:
            response = requests.get(link)
            if response.status_code != 200:
                print(f"Status code {response.status_code} was received when clicking the link: {link}.")
                return False
        except Exception as e:
            print(f"An exception occurred clicking the link: {link}.\n{e}")
            return False
    return True

def move_email(mail, message_id, label):
    try:
        mail.move([message_id], label)
        mail.remove_flags([message_id], ["\\Seen"])
    except Exception as e:
        print(f"Could not move email to {label}.\n{e}")

def read_approved_domains():
    file = open(APPROVED_DOMAINS_FILE, "r")
    domains = [domain for domain in file]
    if domains:
        print("Successfully read the list of approved domains!")
        print("\n".join(domains))
    return domains

def main():
    load_dotenv()
    username = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    mail = connect_to_mail(username, password)

    approved_domains = read_approved_domains()

    while True:
        try:
            fetch_results = read_emails(mail)
            if fetch_results:
                message_unsubscribe_links = search_for_links(fetch_results, approved_domains)
                if message_unsubscribe_links:
                    for message_id, unsubscribe_links in message_unsubscribe_links.items():
                        if click_links(unsubscribe_links):
                            move_email(mail, message_id, "unsubscribed")
                        else:
                            move_email(mail, message_id, "to-unsubscribe")
        except Exception as e:
            print(f"An error occurred, re-logging into email and retrying.\n{e}")
            traceback.print_exc()
            mail = connect_to_mail(username, password)


if __name__ == '__main__':
   main()
