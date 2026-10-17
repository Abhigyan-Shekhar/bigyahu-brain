MATCH p=(a:Symbol {repo_id:'demo:urllib3:browser:eligible',qualname:'HTTPConnectionPool.urlopen'})-[:CALLS]->(b:Symbol {qualname:'set_file_position'}) RETURN p
