import json
from datetime import date
import logging
import feedparser
import html2text
import concurrent.futures
import time

from app.gpt import get_answer_from_llama_web, get_answer_from_chatGPT

with open("app/data/hot_news_rss.json", "r") as f:
    rss_urls = json.load(f)

TODAY = today = date.today()
MAX_DESCRIPTION_LENGTH = 300
MAX_POSTS = 10

isHarvestWeb = False


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

def get_url_summary_from_gpt_thread(url):
    news_summary_prompt = '请用中文简短概括这篇文章的内容。'
    gpt_response, total_llm_model_tokens, total_embedding_model_tokens = get_answer_from_llama_web([news_summary_prompt], [url])
    logging.info(f"=====> GPT response: {gpt_response} (total_llm_model_tokens: {total_llm_model_tokens}, total_embedding_model_tokens: {total_embedding_model_tokens}")
    return str(gpt_response)

def get_translation_from_gpt_thread(description):
    news_translation_prompt = '请用中文翻译：\n' + description
    gpt_response, total_llm_model_tokens, total_embedding_model_tokens = get_answer_from_chatGPT([news_translation_prompt])
    logging.info(f"=====> GPT response: {gpt_response} (total_llm_model_tokens: {total_llm_model_tokens}, total_embedding_model_tokens: {total_embedding_model_tokens}")
    return str(gpt_response)

def get_summary_from_gpt_thread(description):
    news_translation_prompt = '请用中文简短给出下面这段文字的摘要，并且列出其中可能存在的 AI 工具产品。摘要与工具产品间以两行换行符分隔。\n' + description
    gpt_response, total_llm_model_tokens, total_embedding_model_tokens = get_answer_from_chatGPT([news_translation_prompt])
    logging.info(f"=====> GPT response: {gpt_response} (total_llm_model_tokens: {total_llm_model_tokens}, total_embedding_model_tokens: {total_embedding_model_tokens}")
    logging.info("==============get_summary_from_gpt_thread DONE===================")
    time.sleep(2) 
    return str(gpt_response)

def get_summary_from_gpt(url):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(get_url_summary_from_gpt_thread, url)
        return future.result(timeout=300)

def get_translation_from_gpt(description):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(get_translation_from_gpt_thread, description)
        return future.result(timeout=300)

def get_description(entry):
    gpt_answer = None
    summary = None
    global isHarvestWeb

    #如果是 productHunt, HackerNews， V2ex, V2ex, 雪球，就使用抓取网页内容进行摘要。
    #如果是国内 description 是真的简介，少于多少字的。
    #如果是国内 description 是全文的，则。

    logging.info("get_description")
    logging.info(isHarvestWeb)

    if isHarvestWeb:
        try:
            gpt_answer = get_summary_from_gpt(entry.link)
        except Exception as e:
            logging.error(e)
        if gpt_answer is not None:
            summary = 'AI: ' + gpt_answer
        else:
            summary = cut_string(get_text_from_html(entry.summary))
    else:
        if entry.description != None and len(entry.description) > 0:
            if len(entry.description) < 300:
                summary = get_text_from_html(entry.description)
                logging.info("<300" + summary)
            else:
                try:
                    summary = get_summary_from_gpt_thread(get_text_from_html(entry.description))
                    #summary = cut_string(get_text_from_html(entry.description))
                except Exception as e:
                    logging.error(e)
                if summary is not None:
                    summary = 'AI: ' + summary
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

    logging.info(f"==============================={rss_url}===========================================")
    logging.info(f"==============================={rss_url}===========================================")
    logging.info(f"==============================={rss_url}===========================================")

    global isHarvestWeb
    
    isHarvestWeb = False
    match = ['hackernews']
    if any (c in rss_url for c in match):
        isHarvestWeb = True
    
    logging.info(isHarvestWeb)

    for entry in feed.entries:
        published_time = entry.published_parsed if 'published_parsed' in entry else None
        # published_date = date(published_time.tm_year,
        #                       published_time.tm_mon, published_time.tm_mday)
        logging.info(entry.title)
        updated_post = {}
        updated_post['title'] = entry.title
        updated_post['summary'] = get_description(entry)
        updated_post['url'] = entry.link
        updated_post['publish_date'] = published_time
        updated_posts.append(updated_post)
        if len(updated_posts) >= MAX_POSTS:
            break
    
    isHarvestWeb = False

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
#    logging.info(f"build_slack_blocks req title: {title}， news: {news}")
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
#    logging.info(hot_news)
    hot_news_blocks = build_slack_blocks(
        rss['name'], hot_news)
#    logging.info(hot_news_blocks)
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

def build_github_trending_hot_news_blocks():
    return build_hot_news_blocks('github-daily-trending')

def build_36kr_newsflashes_AI_blocks():
    return build_hot_news_blocks('36kr-newsflashes-AI')

def build_36kr_articles_AI_blocks():
    return build_hot_news_blocks('36kr-articles-AI')




def build_csdngeeknews_blocks():
    return build_hot_news_blocks('CSDN-csdngeeknews')

def build_csdnnews_blocks():
    return build_hot_news_blocks('CSDN-csdnnews')

def build_InfoQ_AI_LLM_blocks():
    return build_hot_news_blocks('InfoQ-AI-LLM')

def build_qbitai_News_blocks():
    return build_hot_news_blocks('qbitai-News')

def build_jiqizhixin_News_blocks():
    return build_hot_news_blocks('jiqizhixin-News')

def build_geekpark_News_blocks():
    return build_hot_news_blocks('geekpark-News')

def build_zhidx_News_blocks():
    return build_hot_news_blocks('zhidx-News')


def build_all_news_block():
#    with concurrent.futures.ThreadPoolExecutor() as executor:

#        openai_news = executor.submit(build_openai_hot_news_blocks)
        # twitter_0_news =  executor.submit(build_twitter_0_hot_news_blocks)
        # twitter_1_news =  executor.submit(build_twitter_1_hot_news_blocks)
        # twitter_2_news =  executor.submit(build_twitter_2_hot_news_blocks)

#        v2ex_news = executor.submit(build_v2ex_hot_news_blocks)
#        reddit_news = executor.submit(build_reddit_news_hot_news_blocks)
#        hackernews_news = executor.submit(build_hackernews_news_hot_news_blocks)
#        producthunt_news = executor.submit(build_producthunt_news_hot_news_blocks)
#        xueqiu_news = executor.submit(build_xueqiu_news_hot_news_blocks)

        # github_news = executor.submit(build_github_trending_hot_news_blocks)
        # kr_newsflashes_AI = executor.submit(build_36kr_newsflashes_AI_blocks)
        # kr_articles_AI = executor.submit(build_36kr_articles_AI_blocks)
        # csdngeeknews = executor.submit(build_csdngeeknews_blocks)
        # csdnnews = executor.submit(build_csdnnews_blocks)
        # InfoQ_AI_LLM = executor.submit(build_InfoQ_AI_LLM_blocks)
        # qbitai_News = executor.submit(build_qbitai_News_blocks)
        # jiqizhixin_News = executor.submit(build_jiqizhixin_News_blocks)
        # geekpark_News = executor.submit(build_geekpark_News_blocks)
        # zhidx_News = executor.submit(build_zhidx_News_blocks)


        hackernews_news = build_hackernews_news_hot_news_blocks()
        producthunt_news = build_producthunt_news_hot_news_blocks()
        github_news = build_github_trending_hot_news_blocks()
        kr_newsflashes_AI = build_36kr_newsflashes_AI_blocks()
        kr_articles_AI = build_36kr_articles_AI_blocks()
        csdngeeknews = build_csdngeeknews_blocks()
        csdnnews = build_csdnnews_blocks()
        InfoQ_AI_LLM = build_InfoQ_AI_LLM_blocks()
        qbitai_News = build_qbitai_News_blocks()
        jiqizhixin_News = build_jiqizhixin_News_blocks()
        geekpark_News = build_geekpark_News_blocks()
        zhidx_News = build_zhidx_News_blocks()


#        openai_news_block = openai_news.result()
        # twitter_0_news_block = twitter_0_news.result()
        # twitter_1_news_block = twitter_1_news.result()
        # twitter_2_news_block = twitter_2_news.result()

#        v2ex_news_block = v2ex_news.result()
#        reddit_news_block = reddit_news.result()
#        hackernews_news_block = hackernews_news.result()
#        producthunt_news_block = producthunt_news.result()
#        xueqiu_news_block = xueqiu_news.result()

        hackernews_news_block = hackernews_news
        producthunt_news_block = producthunt_news
        github_news_block = github_news
        kr_newsflashes_AI_blocks = kr_newsflashes_AI
        kr_articles_AI_blocks = kr_articles_AI
        csdngeeknews_blocks = csdngeeknews
        csdnnews_blocks = csdnnews
        InfoQ_AI_LLM_blocks = InfoQ_AI_LLM
        qbitai_News_blocks = qbitai_News
        jiqizhixin_News_blocks = jiqizhixin_News
        geekpark_News_blocks = geekpark_News
        zhidx_News_blocks = zhidx_News

        return [hackernews_news_block,producthunt_news_block,github_news_block, kr_newsflashes_AI_blocks,
            kr_articles_AI_blocks,csdngeeknews_blocks,csdnnews_blocks,InfoQ_AI_LLM_blocks,
            jiqizhixin_News_blocks,zhidx_News_blocks,qbitai_News_blocks,geekpark_News_blocks]

