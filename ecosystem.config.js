module.exports = {
  apps: [{
    name: "cofre-quantitativo",
    script: "./realtime_main.py",
    interpreter: "python3",
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: "500M",
    exp_backoff_restart_delay: 100,
    env: {
      ENVIRONMENT: "production"
    }
  }]
};
