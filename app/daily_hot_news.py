import json
from datetime import date
import logging
import feedparser
import html2text
import concurrent.futures

from app.gpt import get_answer_from_llama_web, get_answer_from_chatGPT

with open("app/data/hot_news_rss.json", "r") as f:
    rss_urls = json.load(f)

TODAY = today = date.today()
MAX_DESCRIPTION_LENGTH = 300
MAX_POSTS = 5


def cut_string(text):
    words = text.split()
    new_text = ""
    count = 0
    for word in words:
        if len(new_text + word) > MAX_DESCRIPTION_LENGTH:
            break
        new_text += word + " "
        count += 1

    return new_text.strip() + '...'

def get_summary_from_gpt_thread(url):
    news_summary_prompt = '请用中文简短概括这篇文章的内容。'
    gpt_response, total_llm_model_tokens, total_embedding_model_tokens = get_answer_from_llama_web([news_summary_prompt], [url])
    logging.info(f"=====> GPT response: {gpt_response} (total_llm_model_tokens: {total_llm_model_tokens}, total_embedding_model_tokens: {total_embedding_model_tokens}")
    return str(gpt_response)

def get_translation_from_gpt_thread(description):
    news_translation_prompt = '请用中文翻译：\n' + description
    gpt_response, total_llm_model_tokens, total_embedding_model_tokens = get_answer_from_chatGPT([news_translation_prompt])
    logging.info(f"=====> GPT response: {gpt_response} (total_llm_model_tokens: {total_llm_model_tokens}, total_embedding_model_tokens: {total_embedding_model_tokens}")
    return str(gpt_response)

def get_summary_from_gpt(url):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(get_summary_from_gpt_thread, url)
        return future.result(timeout=300)

def get_translation_from_gpt(description):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(get_translation_from_gpt_thread, description)
        return future.result(timeout=300)

def get_description(entry):
    gpt_answer = None

    try:
        gpt_answer = get_summary_from_gpt(entry.link)
    except Exception as e:
        logging.error(e)
    if gpt_answer is not None:
        summary = 'AI: ' + gpt_answer
    else:
        summary = cut_string(get_text_from_html(entry.summary))
    return summary

def get_translation(description):
    gpt_answer = None

    try:
        gpt_answer = get_translation_from_gpt(description)
    except Exception as e:
        logging.error(e)
    if gpt_answer is not None:
        summary = 'AI: ' + gpt_answer
    else:
        summary = cut_string(get_text_from_html(description))
    return summary

def get_text_from_html(html):
    text_maker = html2text.HTML2Text()
    text_maker.ignore_links = True
    text_maker.ignore_tables = False
    text_maker.ignore_images = True
    return text_maker.handle(html)

def get_post_urls_with_title(rss_url):
    feed = feedparser.parse(rss_url)
    updated_posts = []
    
    for entry in feed.entries:
        published_time = entry.published_parsed if 'published_parsed' in entry else None
        # published_date = date(published_time.tm_year,
        #                       published_time.tm_mon, published_time.tm_mday)
        updated_post = {}
        updated_post['title'] = entry.title
        updated_post['summary'] = get_description(entry)
        updated_post['url'] = entry.link
        updated_post['publish_date'] = published_time
        updated_posts.append(updated_post)
        if len(updated_posts) >= MAX_POSTS:
            break
        
    return updated_posts

def get_twitter_post_urls_with_title(rss_url):
    feed = feedparser.parse(rss_url)
    updated_posts = []
    
    for entry in feed.entries:
        published_time = entry.published_parsed if 'published_parsed' in entry else None
        # published_date = date(published_time.tm_year,
        #                       published_time.tm_mon, published_time.tm_mday)
        updated_post = {}

        # title: short of title
        # summry： translation of title using GPT
        updated_post['title'] = cut_string(get_text_from_html(entry.title))
        updated_post['summary'] = get_translation(get_text_from_html(entry.title))

        updated_post['url'] = entry.link
        updated_post['publish_date'] = published_time
        updated_posts.append(updated_post)
        if len(updated_posts) >= MAX_POSTS:
            break
        
    return updated_posts


def build_slack_blocks(title, news):
    logging.info(f"build_slack_blocks req title: {title}， news: {news}")
    logging.info("test11111")
    content = []

    for news_item in news:
        content.append([{
            "tag": "a",
            "text": news_item['title'],
            "href": news_item['url']
        }])
        content.append([{
            "tag": "text",
            "text": news_item['summary']
        }])
        content.append([{
            "tag": "text",
            "text": ""
        }])
    data = {
        "zh_cn": {
            "title": f"{title} # {TODAY.strftime('%Y-%m-%d')}",
            "content": content
        }
    }

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{title} # {TODAY.strftime('%Y-%m-%d')}"
            }
        }]
    for news_item in news:
        blocks.extend([{
            "type": "section",
            "text": {
                "text": f"*{news_item['title']}*",
                "type": "mrkdwn"
            },
        }, {
            "type": "section",
            "text": {
                "text": f"{news_item['summary']}",
                "type": "plain_text"
            },
        }, {
            "type": "section",
            "text": {
                "text": f"原文链接：<{news_item['url']}>",
                "type": "mrkdwn"
            },
        }, {
            "type": "divider"
        }])
    return [data, blocks]

def build_hot_news_blocks(news_key):
    rss = rss_urls[news_key]['rss']['hot']
    hot_news = get_post_urls_with_title(rss['url'])
    hot_news_blocks = build_slack_blocks(
        rss['name'], hot_news)
    return hot_news_blocks

def build_twitter_hot_news_blocks(news_key):
    rss = rss_urls[news_key]['rss']['hot']
    hot_news = get_twitter_post_urls_with_title(rss['url'])
    hot_news_blocks = build_slack_blocks(
        rss['name'], hot_news)
    return hot_news_blocks

def build_openai_hot_news_blocks():
    return build_hot_news_blocks('OpenAI')

def build_twitter_0_hot_news_blocks():
    return build_twitter_hot_news_blocks('twitter-0')

def build_twitter_1_hot_news_blocks():
    return build_twitter_hot_news_blocks('twitter-1')

def build_twitter_2_hot_news_blocks():
    return build_twitter_hot_news_blocks('twitter-2')

def build_v2ex_hot_news_blocks():
    return build_hot_news_blocks('v2ex')

def build_reddit_news_hot_news_blocks():
    return build_hot_news_blocks('reddit-news')

def build_hackernews_news_hot_news_blocks():
    return build_hot_news_blocks('hackernews')

def build_producthunt_news_hot_news_blocks():
    return build_hot_news_blocks('producthunt')

def build_xueqiu_news_hot_news_blocks():
    return build_hot_news_blocks('xueqiu')


def build_all_news_block():
    with concurrent.futures.ThreadPoolExecutor() as executor:

        openai_news = executor.submit(build_openai_hot_news_blocks)
        twitter_0_news =  executor.submit(build_twitter_0_hot_news_blocks)
        twitter_1_news =  executor.submit(build_twitter_1_hot_news_blocks)
        twitter_2_news =  executor.submit(build_twitter_2_hot_news_blocks)

        v2ex_news = executor.submit(build_v2ex_hot_news_blocks)
#        reddit_news = executor.submit(build_reddit_news_hot_news_blocks)
        hackernews_news = executor.submit(build_hackernews_news_hot_news_blocks)
        producthunt_news = executor.submit(build_producthunt_news_hot_news_blocks)
        xueqiu_news = executor.submit(build_xueqiu_news_hot_news_blocks)

        openai_news_block = openai_news.result()
        twitter_0_news_block = twitter_0_news.result()
        twitter_1_news_block = twitter_1_news.result()
        twitter_2_news_block = twitter_2_news.result()

        v2ex_news_block = v2ex_news.result()
#        reddit_news_block = reddit_news.result()
        hackernews_news_block = hackernews_news.result()
        producthunt_news_block = producthunt_news.result()
        xueqiu_news_block = xueqiu_news.result()

        return [openai_news_block, v2ex_news_block, twitter_0_news_block, twitter_1_news_block, twitter_2_news_block,
                            hackernews_news_block, producthunt_news_block, xueqiu_news_block]
