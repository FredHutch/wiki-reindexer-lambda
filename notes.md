- Need to install a plugin to make dependencies in a virtualenv visible
  to lambda functions running in AWS (don't need it for local invocations).
https://www.npmjs.com/package/serverless-python-requirements
sls plugin install -n serverless-python-requirements

also worth reading:
https://github.com/UnitedIncome/serverless-python-requirements
https://serverless.com/blog/serverless-python-packaging/

