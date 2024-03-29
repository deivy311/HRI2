# pylint:disable-msg=E0611,I1101
"""
All functions related to XML generation, processing and validation.
"""

## This file is available from https://github.com/adbar/trafilatura
## under GNU GPL v3 license

import json
import logging
import pickle

from io import StringIO
from lxml import etree

import pkg_resources

from .utils import sanitize

import re


LOGGER = logging.getLogger(__name__)
# validation
TEI_SCHEMA = pkg_resources.resource_filename('trafilatura', 'data/tei-schema.pickle')
TEI_VALID_TAGS = {'body', 'cell', 'code', 'del', 'div', 'fw', 'head', 'hi', 'item', \
                  'lb', 'list', 'p', 'quote', 'row', 'table'}
TEI_VALID_ATTRS = {'rend', 'rendition', 'role', 'type'}
TEI_RELAXNG = None # to be downloaded later if necessary

CONTROL_PARSER = etree.XMLParser(remove_blank_text=True)


def build_json_output(docmeta, postbody, commentsbody):
    '''Build JSON output based on extracted information'''
    outputdict = docmeta
    outputdict['source'] = outputdict.pop('url')
    outputdict['source-hostname'] = outputdict.pop('hostname')
    outputdict['excerpt'] = outputdict.pop('description')
    outputdict['categories'] = ';'.join(outputdict['categories'])
    outputdict['tags'] = ';'.join(outputdict['tags'])
    outputdict['text'] = xmltotxt(postbody)
    outputdict['comments'] = xmltotxt(commentsbody)
    return json.dumps(outputdict)


def build_xml_output(postbody, commentsbody):
    '''Build XML output tree based on extracted information'''
    output = etree.Element('doc')
    postbody.tag = 'main'
    output.append(postbody)
    if commentsbody is not None:
        commentsbody.tag = 'comments'
        output.append(commentsbody)
# XML invalid characters
# https://chase-seibert.github.io/blog/2011/05/20/stripping-control-characters-in-python.html
    return output


def control_xml_output(output_tree, output_format, tei_validation, docmeta):
    '''Make sure the XML output is conform and valid if required'''
    control_string = sanitize(etree.tostring(output_tree, encoding='unicode'))
    # necessary for cleaning
    output_tree = etree.fromstring(control_string, CONTROL_PARSER)
    # validate
    if output_format == 'xmltei' and tei_validation is True:
        result = validate_tei(output_tree)
        LOGGER.info('TEI validation result: %s %s %s', result, docmeta['id'], docmeta['url'])
    return etree.tostring(output_tree, pretty_print=True, encoding='unicode').strip()


def add_xml_meta(output, docmeta):
    '''Add extracted metadata to the XML output tree'''
    # metadata
    if docmeta:
        if docmeta['sitename'] is not None:
            output.set('sitename', docmeta['sitename'])
        if docmeta['title'] is not None:
            output.set('title', docmeta['title'])
        if docmeta['author'] is not None:
            output.set('author', docmeta['author'])
        if docmeta['date'] is not None:
            output.set('date', docmeta['date'])
        if docmeta['url'] is not None:
            output.set('source', docmeta['url'])
        if docmeta['hostname'] is not None:
            output.set('hostname', docmeta['hostname'])
        if docmeta['description'] is not None:
            output.set('excerpt', docmeta['description'])
        if docmeta['categories'] is not None:
            output.set('categories', ';'.join(docmeta['categories']))
        if docmeta['tags'] is not None:
            output.set('tags', ';'.join(docmeta['tags']))
        if docmeta['id'] is not None:
            output.set('id', docmeta['id'])
    return output


def build_tei_output(postbody, commentsbody, docmeta):
    '''Build TEI-XML output tree based on extracted information'''
    # build TEI tree
    output = write_teitree(postbody, commentsbody, docmeta)
    # filter output (strip unwanted elements), just in case
    # check and repair
    output = check_tei(output, docmeta['url'])
    return output


def check_tei(tei, url):
    '''Check if the resulting XML file is conform and scrub remaining tags'''
    # convert head tags
    for elem in tei.iter('head'):
        elem.tag = 'fw'
        elem.set('type', 'header')
    # look for elements that are not valid
    for element in tei.xpath('//text/body//*'):
        # check elements
        if element.tag not in TEI_VALID_TAGS:
            # disable warnings for chosen categories
            # if element.tag not in ('div', 'span'):
            LOGGER.warning('not a TEI element, removing: %s %s', element.tag, url)
            merge_with_parent(element)
            continue
        # check attributes
        for attribute in element.attrib:
            if attribute not in TEI_VALID_ATTRS:
                LOGGER.warning('not a valid TEI attribute, removing: %s in %s %s', attribute, element.tag, url)
                element.attrib.pop(attribute)
    # export metadata
    #metadata = (title + '\t' + date + '\t' + uniqueid + '\t' + url + '\t').encode('utf-8')
    return tei


def validate_tei(tei):  # , filename=""
    '''Check if an XML document is conform to the guidelines of the Text Encoding Initiative'''
    global TEI_RELAXNG
    if TEI_RELAXNG is None:
        # load validator
        with open(TEI_SCHEMA, 'rb') as schemafile:
            schema_data = pickle.load(schemafile)
        relaxng_doc = etree.parse(StringIO(schema_data))
        TEI_RELAXNG = etree.RelaxNG(relaxng_doc)
    result = TEI_RELAXNG.validate(tei)
    if result is False:
        print(TEI_RELAXNG.error_log.last_error)
    return result


def replace_element_text(element):
    '''Determine element text based on text and tail'''
    full_text = ''
    if element.text is not None and element.tail is not None:
        full_text = ' '.join([element.text, element.tail])
    elif element.text is not None and element.tail is None:
        full_text = element.text
    elif element.text is None and element.tail is not None:
        full_text = element.tail
    return full_text


def merge_with_parent(element):
    '''Merge element with its parent'''
    parent = element.getparent()
    if parent is None:
        return
    full_text = replace_element_text(element)
    previous = element.getprevious()
    if previous is not None:
        # There is a previous node, append text to its tail
        if previous.tail is not None:
            previous.tail = ' '.join([previous.tail, full_text])
        else:
            previous.tail = full_text
    else:
        # It's the first node in <parent/>, append to parent's text
        if parent.text is not None:
            parent.text = ' '.join([parent.text, full_text])
        else:
            parent.text = full_text
    parent.remove(element)
def text_process2(text_var,explicity=False):
    excluded_specific_words2=["faq","$","&",":","linked","choose","doctor","resource:","resources:","from:","source:","sources:","feature:","features:","center","solution:","sponsor","subscribe","click","submit","Policy","Privacy","question","quiz","multimedia","slide","test","learn","discover","appointment"]
    if explicity:
        for ex_words in excluded_specific_words2:
            if ex_words in text_var.lower():
             text_var=""
    return text_var
def text_process(text_var,explicity=False,special_string=""):
    new_text=re.sub(r'<.+?>', '', text_var)
    new_text=new_text.replace('_','')
    excluded_words=["sources:","from:"]
    excluded_specific_words=["resource","from","source","feature","center","solution","sponsor","subscribe","click","submit","Policy","Privacy","question","quiz","multimedia","slide","test","learn","discover"]
    if special_string!="":
        excluded_words.append(special_string)
    for ex_words in excluded_words:
        if ex_words in new_text.lower():
            new_text=""
    if explicity:
        for ex_words in excluded_specific_words:
            if ex_words.lower() in new_text.lower():
             new_text=""
    return new_text
def xmltotxt(xmloutput):
    '''Convert to plain text format'''
    out_titles={}
    out_main_title={}
    returnlist = []
    # etree.strip_tags(xmloutput, 'div', 'main', 'span')
    # remove and insert into the previous tag
    for element in xmloutput.xpath('//hi|//link'):
        merge_with_parent(element)
        if element.tag=='hi' and (element.text!='' and element.text!=None ):
            # element = element.replace("_", "")# solving strange  characters issue
            new_text=text_process(element.text,explicity=True)
            out_titles[new_text]=""
        continue
    # iterate and convert to list of strings
    flat1=False
    flat_title=""
    flat_head=False
    flat_head_name=""
    for element in xmloutput.iter():
        # process text
        if element.text is None and element.tail is None:
            # newlines for textless elements
            if element.tag in ('row', 'table'):
                returnlist.append('\n')
            continue
        textelement = replace_element_text(element)
        # if textelement!=None:
        #      textelement=text_process(textelement)# solving strange  characters issue
        if element.tag=='head' and (element.text!='' and element.text!=None ):
            #new_text=text_process(element.text)
            textelement=text_process(textelement,explicity=True)
            out_main_title[textelement]=""
            flat_head=True
            flat_head_name=textelement
        elif(flat_head):
            textelement = text_process(textelement,special_string="?")
            textelement = text_process2(textelement,explicity=True)
            out_main_title[flat_head_name]+=textelement
        if bool(out_titles):
            if textelement in out_titles:
                textelement=text_process(textelement,explicity=True)
                flat_head=False
                flat1=True
                flat_title=textelement
            elif(flat1):
                textelement = text_process(textelement,special_string="?")
                textelement = text_process2(textelement,explicity=True)
                out_titles[flat_title]+=textelement
        if element.tag in ('code', 'fw', 'head', 'lb', 'list', 'p', 'quote', 'row', 'table'):
            returnlist.extend(['\n', textelement, '\n'])
        elif element.tag == 'item':
            returnlist.extend(['\n- ', textelement, '\n'])
        elif element.tag == 'cell':
            returnlist.extend(['|', textelement, '|'])
        elif element.tag == 'comments':
            returnlist.append('\n\n')
        else:
            # print(element.tag)
            returnlist.extend([textelement, ' '])
    out_main_title=without_keys(out_main_title, "")    
    out_titles=without_keys(out_titles, "")    
    return sanitize(''.join(returnlist)),out_main_title,out_titles
def without_keys(d, excluded_keys):
    temp_dic={x: d[x] for x in d if x not in excluded_keys}
  #return {x: d[x] for x in d if x not in excluded_keys}
# def without_values(d, excluded_values):
    return {x: temp_dic[x] for x in temp_dic if temp_dic[x] not in excluded_keys}

def write_teitree(postbody, commentsbody, docmeta):
    '''Bundle the extracted post and comments into a TEI tree'''
    tei = etree.Element('TEI', xmlns='http://www.tei-c.org/ns/1.0')
    header = etree.SubElement(tei, 'teiHeader')
    #if simplified is True:
    #    header = write_simpleheader(header, docmeta)
    #else:
    header = write_fullheader(header, docmeta)
    textelem = etree.SubElement(tei, 'text')
    textbody = etree.SubElement(textelem, 'body')
    # post
    postbody.tag = 'div'
    postbody.set('type', 'entry') # rendition='#pst'
    textbody.append(postbody)
    # comments
    if commentsbody is not None and len(commentsbody) > 0:
        commentsbody.tag = 'div'
        commentsbody.set('type', 'comments') # rendition='#cmt'
        textbody.append(commentsbody)
    return tei


def write_fullheader(header, docmeta):
    '''Write TEI header based on gathered metadata'''
    filedesc = etree.SubElement(header, 'fileDesc')
    bib_titlestmt = etree.SubElement(filedesc, 'titleStmt')
    bib_titlemain = etree.SubElement(bib_titlestmt, 'title', type='main')
    bib_titlemain.text = docmeta['title']
    if docmeta['author']:
        bib_author = etree.SubElement(bib_titlestmt, 'author')
        bib_author.text = docmeta['author']
    publicationstmt_a = etree.SubElement(filedesc, 'publicationStmt')
    publicationstmt_p = etree.SubElement(publicationstmt_a, 'p')
    if docmeta['id'] is not None:
        idno = etree.SubElement(publicationstmt_a, 'idno', type='id')
        idno.text = docmeta['id']
    sourcedesc = etree.SubElement(filedesc, 'sourceDesc')
    source_bibl = etree.SubElement(sourcedesc, 'bibl')
    if docmeta['sitename'] and docmeta['date']:
        sigle = docmeta['sitename'] + ', ' + docmeta['date']
    elif not docmeta['sitename'] and docmeta['date']:
        sigle = docmeta['date']
    elif docmeta['sitename'] and not docmeta['date']:
        sigle = docmeta['sitename']
    else:
        sigle = ''
    if docmeta['title']:
        source_bibl.text = docmeta['title'] + '. ' + sigle
    else:
        source_bibl.text = '. ' + sigle
    source_sigle = etree.SubElement(sourcedesc, 'bibl', type='sigle')
    source_sigle.text = sigle
    biblfull = etree.SubElement(sourcedesc, 'biblFull')
    bib_titlestmt = etree.SubElement(biblfull, 'titleStmt')
    bib_titlemain = etree.SubElement(bib_titlestmt, 'title', type='main')
    bib_titlemain.text = docmeta['title']
    if docmeta['author']:
        bib_author = etree.SubElement(bib_titlestmt, 'author')
        bib_author.text = docmeta['author']
    publicationstmt = etree.SubElement(biblfull, 'publicationStmt')
    publication_publisher = etree.SubElement(publicationstmt, 'publisher')
    if docmeta['hostname'] is not None:
        publisherstring = docmeta['sitename'] + '(' + docmeta['hostname'] + ')'
    else:
        publisherstring = docmeta['sitename']
    publication_publisher.text = publisherstring
    if docmeta['url'] is not None:
        publication_url = etree.SubElement(publicationstmt, 'ptr', type='URL', target=docmeta['url'])
    publication_date = etree.SubElement(publicationstmt, 'date')
    publication_date.text = docmeta['date']
    profiledesc = etree.SubElement(header, 'profileDesc')
    abstract = etree.SubElement(profiledesc, 'abstract')
    abstract_p = etree.SubElement(abstract, 'p')
    abstract_p.text = docmeta['description']
    if len(docmeta['categories']) > 0 or len(docmeta['tags']) > 0:
        textclass = etree.SubElement(profiledesc, 'textClass')
        keywords = etree.SubElement(textclass, 'keywords')
        if len(docmeta['categories']) > 0:
            cat_list = etree.SubElement(keywords, 'term', type='categories')
            cat_list.text = ','.join(docmeta['categories'])
        if len(docmeta['tags']) > 0:
            tags_list = etree.SubElement(keywords, 'term', type='tags')
            tags_list.text = ','.join(docmeta['tags'])
    encodingdesc = etree.SubElement(header, 'encodingDesc')
    appinfo = etree.SubElement(encodingdesc, 'appInfo')
    application = etree.SubElement(appinfo, 'application', version=pkg_resources.get_distribution('trafilatura').version, ident='Trafilatura')
    label = etree.SubElement(application, 'label')
    label.text = 'Trafilatura'
    pointer = etree.SubElement(application, 'ptr', target='https://github.com/adbar/trafilatura')
    return header
