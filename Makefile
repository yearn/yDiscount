include .env
export

dev:
	@tmux new-session -d -s devenv
	@tmux splitw -h -p 50
	@tmux send-keys -t devenv:0.0 'source .venv/bin/activate && ape run dev && ape console' C-m
	@tmux send-keys -t devenv:0.1 'anvil --host 0.0.0.0 -f $$HTTPS_ARCHIVE_RPC_1 --chain-id 1337 --block-base-fee-per-gas 1000000000' C-m
	@tmux selectp -t 0
	@tmux attach-session -t devenv
