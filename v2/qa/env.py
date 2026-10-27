"""All mutable QA state stays under this port. Never invokes rustup/installers."""
import os,pathlib,subprocess,sys
V2=pathlib.Path(__file__).resolve().parents[1]
QA=V2/'.qa'
def env(toolchain='stable',fresh=False):
    tool=pathlib.Path('/Users/almat/.rustup/toolchains')/(toolchain+'-aarch64-apple-darwin')
    e={'PATH':str(tool/'bin')+':/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin', 'HOME':str(QA/'home'),'TMPDIR':str(QA/'tmp'),'TMP':str(QA/'tmp'),'TEMP':str(QA/'tmp'),'CARGO_HOME':str(QA/('fresh-cargo' if fresh else 'cargo')),'CARGO_TARGET_DIR':str(V2/('target/fresh' if fresh else 'target')/toolchain),'XDG_CACHE_HOME':str(QA/'xdg/cache'),'XDG_CONFIG_HOME':str(QA/'xdg/config'),'XDG_DATA_HOME':str(QA/'xdg/data'),'npm_config_cache':str(QA/'npm-cache'),'npm_config_userconfig':str(QA/'npmrc'),'npm_config_globalconfig':str(QA/'global-npmrc'),'CARGO_NET_GIT_FETCH_WITH_CLI':'false','CARGO_BUILD_JOBS':'4','CARGO_RESOLVER_INCOMPATIBLE_RUST_VERSIONS':'fallback','PYTHONDONTWRITEBYTECODE':'1','CI':'1','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':str(QA/'gitconfig')}
    for k in ['HOME','TMPDIR','CARGO_HOME','CARGO_TARGET_DIR','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','npm_config_cache']:pathlib.Path(e[k]).mkdir(parents=True,exist_ok=True)
    return e
def run(args,**kw):return subprocess.run(args,env=env(),check=True,**kw)
if __name__=='__main__':
    args=sys.argv[1:]; tool='stable'
    if args and args[0] in ('stable','1.85.0'):tool=args.pop(0)
    raise SystemExit(subprocess.call(args,env=env(tool),cwd=V2))
