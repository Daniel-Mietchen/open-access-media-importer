#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date
from os import listdir, path
from urllib2 import urlopen, urlparse
from xml.etree.cElementTree import dump, ElementTree
# the C implementation of ElementTree is 5 to 20 times faster than the Python one

import tarfile

# According to <ftp://ftp.ncbi.nlm.nih.gov/README.ftp>, this should be
# 33554432 (32MiB) for best performance. Note that on slow connections,
# however, huge buffers size leads to notable interface lag.
BUFSIZE = 33554432
#BUFSIZE = 1024000  # (1024KB)

def download_metadata(target_directory):
    """
    Downloads files from PubMed FTP server into given directory.
    """
    urls = [
        'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/articles.A-B.tar.gz',
        'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/articles.C-H.tar.gz',
        'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/articles.I-N.tar.gz',
        'ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/articles.O-Z.tar.gz'
    ]

    for url in urls:
        remote_file = urlopen(url)
        total = int(remote_file.headers['content-length'])
        completed = 0

        url_path = urlparse.urlsplit(url).path
        local_filename = path.join(target_directory, \
            url_path.split('/')[-1])

        # if local file has same size as remote file, skip download
        try:
            if (path.getsize(local_filename) == total):
                continue
        except OSError:  # local file does not exist
            pass

        with open(local_filename,'wb') as local_file:
            while True:
                chunk = remote_file.read(BUFSIZE)
                if chunk != '':
                    local_file.write(chunk)
                    completed += len(chunk)
                    yield {
                        'url': url,
                        'completed': completed,
                        'total': total
                    }
                else:
                    break

def list_articles(target_directory):
    """
    Iterates over archive files in target_directory, yielding article information.
    """
    listing = listdir(target_directory)
    for filename in listing:
        with tarfile.open(path.join(target_directory, filename)) as archive:
            for item in archive:
                if path.splitext(item.name)[1] == '.nxml':
                    content = archive.extractfile(item)
                    tree = ElementTree()
                    tree.parse(content)

                    result = {}
                    result['article-contrib-authors'] = _get_article_contrib_authors(tree)
                    result['article-title'] = _get_article_title(tree)
                    result['article-abstract'] = _get_article_abstract(tree)
                    result['journal-title'] = _get_journal_title(tree)
                    result['article-date'] = _get_article_date(tree)
                    result['article-url'] = _get_article_url(tree)
                    result['article-license-url'] = _get_article_license_url(tree)
                    result['article-copyright-holder'] = _get_article_copyright_holder(tree)
                    yield result

def _get_article_contrib_authors(tree):
    from sys import stderr
    """
    Given an ElementTree, returns article authors in a format suitable for citation.
    """
    authors = []
    front = ElementTree(tree).find('front')
    for contrib in front.iter('contrib'):
        contribTree = ElementTree(contrib)
        try:
            surname = contribTree.find('name/surname').text
        except AttributeError:  # author is not a natural person
            citation_name = contribTree.find('collab').text
            if citation_name is not None:
                authors.append(citation_name)
            continue

        try:
            given_names = contribTree.find('name/given-names').text
            citation_name = ' '.join([surname, given_names[0]])
        except AttributeError:  # no given names
            citation_name = surname
        except TypeError:  # also no given names
            citation_name = surname
        if citation_name is not None:
            authors.append(citation_name)

    return ', '.join(authors)

def _get_article_title(tree):
    """
    Given an ElementTree, returns article title.
    """
    front = ElementTree(tree).find('front')
    for title in front.iter('article-title'):
        return title.text

def _get_article_abstract(tree):
    # FIXME: this does not work right
    """
    Given an ElementTree, returns article abstract.
    """
    result = []
    front = ElementTree(tree).find('front')
    for abstract in front.iter('abstract'):
        for element in abstract.iter():
            if element.text is not None:
                result.append(element.text)
    return '  '.join(result)

def _get_journal_title(tree):
    """
    Given an ElementTree, returns journal title.
    """
    front = ElementTree(tree).find('front')
    for journal_meta in front.iter('journal-meta'):
        for journal_title in journal_meta.iter('journal-title'):
            return journal_title.text

def _get_article_date(tree):
    """
    Given an ElementTree, returns article date.
    """
    article_meta = ElementTree(tree).find('front/article-meta')
    for pub_date in article_meta.iter('pub-date'):
        if pub_date.attrib['pub-type'] == 'epub':
            pub_date_tree = ElementTree(pub_date)
            year = int(pub_date_tree.find('year').text)
            month = int(pub_date_tree.find('month').text)
            day = int(pub_date_tree.find('day').text)
            return str(date(year, month, day))

def _get_article_url(tree):
    """
    Given an ElementTree, returns article URL.
    """
    article_meta = ElementTree(tree).find('front/article-meta')
    for article_id in article_meta.iter('article-id'):
        if article_id.attrib['pub-id-type'] == 'doi':
            return 'http://dx.doi.org/' + article_id.text

def _get_article_license_url(tree):
    """
    Given an ElementTree, returns article license URL.
    """
    license = ElementTree(tree).find('front/article-meta/permissions/license')
    try:
        return license.attrib['{http://www.w3.org/1999/xlink}href']
    except AttributeError:  # license statement is missing
        return ''
    except KeyError:  # license statement is in plain text
        return ''

def _get_article_copyright_holder(tree):
    """
    Given an ElementTree, returns article copyright holder.
    """
    copyright_holder = ElementTree(tree).find(
        'front/article-meta/permissions/copyright-holder'
    )
    try:
        return copyright_holder.text
    except AttributeError:  # no copyright_holder known
        return ''