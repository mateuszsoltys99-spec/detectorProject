import io
import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

import numpy as np
from PIL import Image


def _parse_smtp_url(smtp_url: str):
    """Parse 'host:port' from SMTP_URL. Port defaults to 25 if omitted."""
    if ":" in smtp_url:
        host, port_str = smtp_url.rsplit(":", 1)
        try:
            return host, int(port_str)
        except ValueError:
            raise ValueError("SMTP_URL port is not a valid integer: {!r}".format(smtp_url))
    return smtp_url, 25


def send_notification(camera_index: int, frame: np.ndarray):
    smtp_url = os.environ["SMTP_URL"]
    smtp_username = os.environ["SMTP_USERNAME"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    smtp_host, smtp_port = _parse_smtp_url(smtp_url)

    sender = "Private Person <from@example.com>"
    receiver = "A Test User <to@example.com>"

    message = MIMEMultipart()
    message["Subject"] = "Suspicious activity on camera {}".format(camera_index)
    message["From"] = sender
    message["To"] = receiver
    message.preamble = "Preview in the attachment"
    outbuf = io.BytesIO()
    Image.fromarray(frame).save(outbuf, format="PNG")
    my_mime_image = MIMEImage(outbuf.getvalue())
    my_mime_image.add_header('Content-Disposition', 'attachment', filename='frame.png')
    outbuf.close()
    message.attach(my_mime_image)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.login(smtp_username, smtp_password)
        server.sendmail(sender, receiver, message.as_string())
