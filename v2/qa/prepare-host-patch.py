"""Write generic UNAPPLIED patches; never touches the host checkout."""
import difflib,pathlib,subprocess,shutil
V=pathlib.Path(__file__).resolve().parents[1]; P=V/'fixtures/pinned/host'; O=V/'.qa/patched-host';O.mkdir(parents=True,exist_ok=True)
changes={}
p='src/renderer/src/raycast-api/list-runtime.tsx';s=(P/p).read_text();t=s.replace("    if (query === lastSentQuery.current) return", "    // Server search is dispatched by the input event, before any debounce.\n    if (hasServerSearch || query === lastSentQuery.current) return").replace('[query, onSearchTextChanged])','[query, onSearchTextChanged, hasServerSearch])').replace('                  setQuery(event.target.value)\n                  setSelected(0)', '                  const draft = event.target.value\n                  setQuery(draft)\n                  setSelected(0)\n                  if (hasServerSearch) {\n                    lastSentQuery.current = draft\n                    void onSearchTextChanged(draft)\n                  }')
# Respect command-owned empty copy instead of application-specific defaults.
t=t.replace("? 'No matching applications'", "? emptyView?.title || 'No matching applications'").replace("? 'Try a different app name or keyword.'", "? emptyView?.description || 'Try a different app name or keyword.'")
# Surface the current search, rather than stale rows alone, during owned HTTP.
t=t.replace("  const hasMore = root.props?.__hasMore === true", "  const hasMore = root.props?.__hasMore === true\n  const isLoading = root.props?.isLoading === true")
t=t.replace("          {filteredRows.length} item", "          {isLoading ? 'Loading… · ' : ''}{filteredRows.length} item")
assert s!=t;changes[p]=(s,t)
p='src/renderer/ExtensionRuntimeView.tsx';s=(P/p).read_text();t=s.replace('      const result = await window.tezbar.extensionSearchTextChanged({', '      setError(null)\n      let result\n      try {\n        result = await window.tezbar.extensionSearchTextChanged({').replace('        searchText,\n      })\n      if (requestSeq', '        searchText,\n        })\n      } catch (error) {\n        if (requestSeq === searchRequestSeq.current && currentSession.current === sessionOwner) {\n          setError(error instanceof Error ? error.message : String(error))\n        }\n        return\n      }\n      if (requestSeq')
t=t.replace("    const result = await window.tezbar.extensionLoadMore({ sessionId: state.sessionId })\n    if (currentSession.current !== sessionOwner) return", "    const requestSeq = searchRequestSeq.current\n    const result = await window.tezbar.extensionLoadMore({ sessionId: state.sessionId })\n    if (requestSeq !== searchRequestSeq.current || currentSession.current !== sessionOwner) return")
t=t.replace("          const result = await window.tezbar.extensionRefreshSession({ sessionId: state.sessionId })\n          if (cancelled", "          const requestSeq = searchRequestSeq.current\n          const result = await window.tezbar.extensionRefreshSession({ sessionId: state.sessionId })\n          if (requestSeq !== searchRequestSeq.current || cancelled")
t=t.replace('              setError(null)\n              const invokedAction', '              const requestSeq = searchRequestSeq.current\n              setError(null)\n              const invokedAction')
t=t.replace('              if (currentSession.current !== sessionOwner) return', '              if (requestSeq !== searchRequestSeq.current || currentSession.current !== sessionOwner) return')
# A thrown old refresh must not leave a permanent visible error after a new search.
t=t.replace('        try {\n          const requestSeq = searchRequestSeq.current', '        const requestSeq = searchRequestSeq.current\n        try {')
t=t.replace('        } catch (error) {\n          if (!cancelled) setError', '        } catch (error) {\n          if (!cancelled && requestSeq === searchRequestSeq.current && currentSession.current === sessionOwner) setError')
t=t.replace("  const searchRequestSeq = useRef(0)", "  const searchRequestSeq = useRef(0)\n  const [searchPending, setSearchPending] = useState(false)")
t=t.replace("    setState(fromRunResult(initial))\n    setError(null)", "    setState(fromRunResult(initial))\n    setError(null)\n    setSearchPending(false)")
t=t.replace("      setError(null)\n      let result", "      setError(null)\n      setSearchPending(true)\n      let result")
t=t.replace("          setError(error instanceof Error ? error.message : String(error))\n        }\n        return", "          setError(error instanceof Error ? error.message : String(error))\n          setSearchPending(false)\n        }\n        return")
t=t.replace("      if (requestSeq !== searchRequestSeq.current || currentSession.current !== sessionOwner) return\n\n      if (!result.ok)", "      if (requestSeq !== searchRequestSeq.current || currentSession.current !== sessionOwner) return\n      setSearchPending(false)\n\n      if (!result.ok)")
t=t.replace("            commandName={state.commandName}\n            root={state.root}", "            commandName={state.commandName}\n            root={{ ...state.root, props: { ...state.root.props, isLoading: searchPending || state.root.props?.isLoading === true } }}")
# Stale action IDs legitimately return SDK unchanged; preserve the current view.
t=t.replace('              const effectNoticeValue = effectNotice(result.effects)', "              if (result.mode === 'unchanged') return\n              const effectNoticeValue = effectNotice(result.effects)")
assert s!=t;changes[p]=(s,t)
p='src/shared/extensionRuntime.ts';s=(P/p).read_text();t=s.replace('export type ExtensionInvokeActionResult =\n', "export type ExtensionInvokeActionResult =\n  | { ok: true; mode: 'unchanged' }\n");assert s!=t;changes[p]=(s,t)
patch=[]
for p,(s,t) in changes.items():
 d=O/p;d.parent.mkdir(parents=True,exist_ok=True);d.write_text(t)
 patch.extend(difflib.unified_diff(s.splitlines(keepends=True),t.splitlines(keepends=True),fromfile='a/'+p,tofile='b/'+p))
(V/'patches/0001-renderer-search-ownership.patch').write_text(''.join(patch))
check=V/'.qa/patch-applied'
for p in changes:
 d=check/p;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(P/p,d)
subprocess.run(['git','apply','--directory=v2/.qa/patch-applied','v2/patches/0001-renderer-search-ownership.patch'],cwd=V.parent,check=True)
for p in changes:assert (check/p).read_bytes()==(O/p).read_bytes()
print('Prepared unapplied renderer patch against ea100cee3f69711de12485ba061950c5fc65258f')
