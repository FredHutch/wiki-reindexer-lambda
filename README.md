# Wiki Reindexer Lambda Functions.

A collection of [AWS Lambda](https://aws.amazon.com/lambda/) functions for tasks related to the 
search engine for the 
[Fred Hutch Biomedical Data Science Wiki](https://sciwiki.fredhutch.org/). The functions are managed and
deployed with the [Serverless](https://aws.amazon.com/lambda/) platform.

## Functions

### push_hook

This function is connected to [AWS API Gateway](https://aws.amazon.com/api-gateway/) so that it is accessible via a URL. This URL is configured as a Web Hook for the
[Wiki Repository](https://github.com/FredHutch/wiki), triggered when there is a push to the repository.

All the function does is invoke the `run_crawler` function and return. This function does not do any crawling on its own because, since it is hooked up to API Gateway, it needs to return in under 30 seconds, 
and crawling may take longer than that.

### run_crawler

This function is invoked by the `push_hook` function.
First, it sleeps for a few minutes to give Jekyll
a chance to build the GitHub Pages site for the wiki.
Then it spiders the site using the [Scrapy](https://scrapy.org/) module, converts HTML to text using 
[Pandoc](https://pandoc.org/), and indexes the text
into our [AWS Elasticsearch](https://aws.amazon.com/elasticsearch-service/) domain. 

### delete_orphans

This function is invoked on a schedule, every 2 hours.

It retrieves all the URLs from the wiki (using the
same spidering mechanism that `run_crawler` uses), and 
also retrieves all URLs that are indexed in Elasticsearch. If there are any URLs in the latter list that are not in the former, they are removed. This
is necessary if any pages are deleted from the wiki, so
we can avoid displaying search results that link to
pages that no longer exist.

## Deploying and developing

### Prerequisites

You need to [install Serverless](https://serverless.com/framework/docs/getting-started/) which in turn involves
[installing NodeJS](https://nodejs.org/en/). If you already have Node installed, [update to the most recent version](https://stackoverflow.com/a/47909570/470769).

After Node is installed, run `npm install` to install
the serverless [plugin](https://github.com/UnitedIncome/serverless-python-requirements) that manages Python dependencies. 

If it's not already installed, install [Python 3.6](https://www.python.org/downloads/release/python-368/). 

Install the `pipenv` package globally (with the command `pip3 install pipenv`). It is used
to manage dependencies in this project. 

#### AWS

Make sure you have access to the SciComp AWS account, and have credentials for it in your `~/.aws/` directory.
If you have multiple AWS account profiles, be sure and 
set the appropriate one using the `AWS_PROFILE` environment variable.


### Development

At the beginning of each develoment session, 
type

```
pipenv shell
```

To activate the project's virtual environment in
your current shell.

In addition to changing Python code, you will
manage the Serverless configuration (in the file
`serverless.yml`). Refer to the 
[Serverless documentation](https://serverless.com/framework/docs/providers/aws/) for information on this file,
as well as the serverless CLI. 

## Notes on developing for the Lambda environment

This is not critical information for maintaining this project. It's relevant to the general topic of developing for the AWS Lambda environment, which is
more limited and quirky than a traditional 
compute environment.

This is just a compilation of issues encountered during
development of this project and their respective solutions.

### 
