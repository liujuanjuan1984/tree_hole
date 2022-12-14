"""treehole bot"""
import datetime
import json
import logging

import requests
from mininode import MiniNode
from mininode.crypto import create_private_key
from mininode.utils import decode_seed_url, get_filebytes
from mixinsdk.clients.blaze_client import BlazeClient
from mixinsdk.clients.http_client import HttpClient_AppAuth
from mixinsdk.clients.user_config import AppConfig
from mixinsdk.types.message import MessageView, pack_contact_data, pack_message, pack_text_data
from mixinsdk.utils import parse_rfc3339_to_datetime

import config_private as PVT

logger = logging.getLogger(__name__)


HTTP_ZEROMESH = "https://mixin-api.zeromesh.net"
BLAZE_ZEROMESH = "wss://mixin-blaze.zeromesh.net"

DEV_MIXIN_ID = PVT.DEV_MIXIN_ID
RSS_MIXIN_ID = PVT.RSS_MIXIN_ID
MIXIN_BOT_KEYSTORE = PVT.MIXIN_BOT_KEYSTORE

PRIVATE_KEY_TYPE = PVT.PRIVATE_KEY_TYPE
SAME_PVTKEY = PVT.SAME_PVTKEY
RUM_SEED_URL = PVT.RUM_SEED_URL
GROUP_NAME = decode_seed_url(RUM_SEED_URL)["group_name"]

TEXT_LENGTH_MIN = 10
TEXT_LENGTH_MAX = 500

WELCOME_TEXT = f"""ð hi, I am TreeHole bot

åæåéå¾çï¼æææ¬ï¼é¿åº¦ä¸ä½äº {TEXT_LENGTH_MIN} ï¼ä¸è¶åº {TEXT_LENGTH_MAX}ï¼ï¼
æå°ä»¥å¯é¥ç­¾åï¼æè¯¥å¾çæææ¬ä»¥âæ æ´âçå½¢å¼åéå° RUM ç§å­ç½ç»{GROUP_NAME}ã

æä¸å­å¨ä»»ä½æ°æ®ï¼è¯·æ¾å¿äº«åçæ­£å¿åçâæ æ´âå§ã

æ³è¦æ¥éå·²åå¸çæ æ´æäºå¨ï¼
è¯·éè¿ Rum åºç¨å å¥ç§å­ç½ç» {GROUP_NAME} æå¨ Mixin ä¸ä½¿ç¨ botï¼{PVT.RSS_MIXIN_ID_NUM}
"""


class TreeHoleBot:
    """init"""

    def __init__(self, mixin_keystore, rum_seedurl):
        self.config = AppConfig.from_payload(mixin_keystore)
        self.rum = MiniNode(rum_seedurl)
        self.xin = HttpClient_AppAuth(self.config, api_base=HTTP_ZEROMESH)


def message_handle_error_callback(error, details):
    """message_handle_error_callback"""
    logger.error("===== error_callback =====")
    logger.error("error: %s", error)
    logger.error("details: %s", details)


async def message_handle(message):
    """message_handle"""
    global bot
    action = message["action"]

    if action == "ERROR":
        logger.warning(message["error"])

    if action != "CREATE_MESSAGE":
        return

    error = message.get("error")
    if error:
        logger.info(str(error))
        return

    msg_data = message.get("data", {})

    msg_id = msg_data.get("message_id")
    if not msg_id:
        await bot.blaze.echo(msg_id)
        return

    msg_type = msg_data.get("type")
    if msg_type != "message":
        await bot.blaze.echo(msg_id)
        return

    # å server æ -8 æ¶å·®ã-9 ä¹å°±æ¯åªå¤ç 1 å°æ¶åç message
    create_at = parse_rfc3339_to_datetime(msg_data.get("created_at"))
    blaze_for_hour = datetime.datetime.now() + datetime.timedelta(hours=-9)
    if create_at <= blaze_for_hour:
        await bot.blaze.echo(msg_id)
        return

    msg_cid = msg_data.get("conversation_id")
    if not msg_cid:
        await bot.blaze.echo(msg_id)
        return

    data = msg_data.get("data")
    if not (data and isinstance(data, str)):
        await bot.blaze.echo(msg_id)
        return

    category = msg_data.get("category")
    if category not in ["PLAIN_TEXT", "PLAIN_IMAGE"]:
        await bot.blaze.echo(msg_id)
        return

    to_send_data = {}
    reply_text = ""
    reply_msgs = []
    is_echo = True

    if category == "PLAIN_TEXT":
        text = MessageView.from_dict(msg_data).data_decoded
        _text_length = f"ææ¬é¿åº¦éå¨ {TEXT_LENGTH_MIN} è³ {TEXT_LENGTH_MAX} ä¹é´"
        if text.lower() in ["hi", "hello", "nihao", "ä½ å¥½", "help", "?", "ï¼"]:
            reply_text = WELCOME_TEXT
        elif len(text) <= TEXT_LENGTH_MIN:
            reply_text = f"æ¶æ¯å¤ªç­ï¼æ æ³å¤çã{_text_length}"
        elif len(text) >= TEXT_LENGTH_MAX:
            reply_text = f"æ¶æ¯å¤ªé¿ï¼æ æ³å¤çã{_text_length}"
        else:
            to_send_data = {"content": "#æ æ´# " + text}
    elif category == "PLAIN_IMAGE":
        try:
            _bytes, _ = get_filebytes(data)
            attachment_id = json.loads(_bytes).get("attachment_id")
            attachment = bot.xin.api.message.read_attachment(attachment_id)
            view_url = attachment["data"]["view_url"]
            content = requests.get(view_url).content  # å¾ç content
            to_send_data = {"content": "#æ æ´# ", "images": [content]}
        except Exception as err:
            to_send_data = None
            is_echo = False
            logger.warning(err)

    if to_send_data:
        if PRIVATE_KEY_TYPE == "SAME":
            pvtkey = SAME_PVTKEY
        else:
            pvtkey = create_private_key()
        try:
            resp = bot.rum.api.send_content(pvtkey, **to_send_data)
            if "trx_id" in resp:
                print(datetime.datetime.now(), resp["trx_id"], "sent_to_rum done.")
                reply_text = f"æ æ´å·²çæ trx {resp['trx_id']}ï¼æ¨æ­¤åå¯éè¿ä¸æ¹ mixin bot æ¥ç {GROUP_NAME} å¨æ"
                reply_msgs.append(pack_message(pack_contact_data(RSS_MIXIN_ID), msg_cid))
            else:
                is_echo = False
        except Exception as err:
            is_echo = False
            logger.warning(err)

    if reply_text:
        reply_msg = pack_message(
            pack_text_data(reply_text),
            conversation_id=msg_cid,
            quote_message_id=msg_id,
        )
        reply_msgs.insert(0, reply_msg)

    if reply_msgs:
        for msg in reply_msgs:
            bot.xin.api.send_messages(msg)

    if is_echo:
        await bot.blaze.echo(msg_id)
    return


bot = TreeHoleBot(MIXIN_BOT_KEYSTORE, RUM_SEED_URL)
bot.blaze = BlazeClient(
    bot.config,
    on_message=message_handle,
    on_message_error_callback=message_handle_error_callback,
    api_base=BLAZE_ZEROMESH,
)
bot.blaze.run_forever(2)
